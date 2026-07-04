# ##== OPENAI RESPONSES API ADAPTER ==##
# Module độc lập — xử lý toàn bộ phần riêng của OpenAI Responses API
# (/v1/responses — khác /v1/chat/completions ở chỗ dùng "input" thay
# "messages", "output" thay "choices", tool định nghĩa "internally tagged"
# (không có wrapper {"type":"function","function":{...}}), và bộ SSE event
# đặt tên riêng: response.output_text.delta, response.output_item.added,
# response.function_call_arguments.delta/done, response.completed...).
#
# THIẾT KẾ: giống hệt pattern 01c_anthropic.py/01b_aws.py — "chỗ chuyển".
# Code cũ (02_provider.py, 09_api_system.py) KHÔNG đổi gì — chỉ rẽ nhánh
# theo format_kind tại đúng vài điểm. Mọi khác biệt của Responses API được
# dịch lại bên trong module này để phía gọi không cần biết.
#
# Hỗ trợ: custom provider thêm qua wizard với format="openai_responses".
#
# Nguồn xác minh (đọc trực tiếp, không đoán field):
#   https://developers.openai.com/api/docs/guides/migrate-to-responses
#   https://developers.openai.com/api/docs/guides/function-calling
#   (mục "Streaming function calls" — có sample event thật, dùng đúng field
#   tên/thứ tự như dưới đây, không suy diễn thêm field ngoài mẫu).


# ── Request builder ──────────────────────────────────────────────────────────
def build_openai_responses_request(path: str, api_key: str, payload: dict | None,
                                    extra_headers: dict | None = None,
                                    base_url: str = "https://api.openai.com/v1",
                                    ) -> "urllib.request.Request":
    """
    Tạo urllib.request.Request cho OpenAI Responses API.
    payload là OpenAI Chat-Completions-style từ call_api_stream() — dịch
    sang Responses API format ("input" thay "messages", tool định nghĩa
    internally-tagged).
    path: "/responses" (chat turn) hoặc "/models" (GET để list models) —
    cùng quy ước path-là-cờ-hiệu như build_anthropic_request().
    """
    url = path if path.startswith("http") else f"{base_url.rstrip('/')}{path}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(_to_responses_payload(payload)).encode()
        method = "POST"

    return urllib.request.Request(url, data=body, headers=headers, method=method)


# ── Payload convert: OpenAI Chat-style → Responses API ──────────────────────
# Convert content blocks: Chat-style (text/image_url) → Responses input content
# Nguồn ảnh DUY NHẤT trong hệ thống là /web (12_web.py) — xem ghi chú tương tự
# ở _convert_content_blocks_to_anthropic() (01c_anthropic.py). Responses API
# dùng "input_text"/"input_image" cho input items (khác "output_text" dùng ở
# phía output) — xác nhận qua ResponseInputImage/ResponseInputText trong docs
# reference (developers.openai.com/api/reference/resources/responses).
def _convert_content_blocks_to_responses(blocks: list) -> list:
    out = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        btype = b.get("type")
        if btype == "text":
            out.append({"type": "input_text", "text": b.get("text", "")})
        elif btype == "image_url":
            url = (b.get("image_url") or {}).get("url", "")
            # Chỉ hỗ trợ data-URI base64 (đúng những gì web client gửi lên) —
            # giữ nguyên convention như 2 adapter kia. ResponseInputImage
            # nhận field "image_url" trực tiếp (string), không lồng dict như
            # Chat Completions — khác cấu trúc "image_url":{"url":...}.
            if url.startswith("data:") and ";base64," in url:
                out.append({"type": "input_image", "image_url": url})
            # else: không phải data-URI base64 hợp lệ — bỏ qua block này
            # thay vì gửi rác lên API (nhất quán với 2 adapter kia).
        # Các type khác — bỏ qua an toàn.
    return out or [{"type": "input_text", "text": ""}]


def _to_responses_payload(payload: dict) -> dict:
    """
    Dịch payload OpenAI Chat-Completions-style (messages, tools, tool_choice,
    max_tokens, stream, temperature...) mà call_api_stream() build sẵn, sang
    format Responses API.

    Mapping đã xác nhận qua migrate-to-responses guide:
      messages[]                  → input (string hoặc list Items)
      system message              → instructions (top-level) HOẶC item
                                     message role dùng nguyên trong input
                                     nếu cần giữ đúng vị trí trong transcript
                                     (ở đây gộp mọi system message thành
                                     "instructions" — đơn giản, đúng 1-1 với
                                     cách 01c_anthropic.py gộp thành "system")
      assistant message có content → output message item role=assistant
                                     (khi replay lại làm input, gửi nguyên
                                     dạng message role=assistant là hợp lệ —
                                     guide xác nhận "simple message inputs
                                     are compatible from one API to the
                                     other" cho trường hợp không dùng
                                     functions/multimodal; ở đây tool_calls
                                     được tách thành item riêng bên dưới)
      assistant tool_calls        → 1 item {"type":"function_call", ...}
                                     MỖI tool_call (không gộp vào message)
      role=tool (kết quả tool)    → 1 item {"type":"function_call_output",
                                     "call_id":..., "output":...}
      max_tokens                  → max_output_tokens (tên field khác)
      tools (function schema)     → internally-tagged: bỏ wrapper
                                     {"type":"function","function":{...}}
                                     thành {"type":"function","name":...,
                                     "description":...,"parameters":...}
                                     trực tiếp ở top-level từng tool —
                                     xác nhận qua "Update function
                                     definitions" trong migrate guide.
    """
    messages_in = payload.get("messages", [])
    instructions_parts: list[str] = []
    input_items: list[dict] = []

    for m in messages_in:
        role = m.get("role")

        if role == "system":
            instructions_parts.append(m.get("content", ""))
            continue

        if role == "tool":
            # function_call_output item — liên kết qua call_id (KHÔNG phải
            # tool_call_id đổi tên suông: field trong Responses API đúng là
            # "call_id", xác nhận qua ví dụ function-calling guide). Mỗi
            # tool result là 1 item RIÊNG (không cần gộp nhiều cái vào 1
            # message như Anthropic/Bedrock — Responses input là 1 list
            # phẳng các Item độc lập, không có ràng buộc "role phải
            # alternate" như 2 format kia).
            input_items.append({
                "type": "function_call_output",
                "call_id": m.get("tool_call_id", ""),
                "output": m.get("content", ""),
            })
            continue

        if role == "assistant":
            # Text content (nếu có) → message item role=assistant, giữ
            # nguyên dạng string content (guide xác nhận input message Item
            # role=assistant hợp lệ để replay lại vào input list).
            if m.get("content"):
                input_items.append({
                    "role": "assistant",
                    "content": m["content"],
                })
            # Mỗi tool_call → 1 item function_call riêng, KHÔNG lồng trong
            # message (khác hẳn Chat Completions gộp tool_calls[] vào cùng
            # 1 message assistant) — xác nhận qua sample response thật ở
            # function-calling guide: output array chứa entry riêng
            # {"type":"function_call","call_id":...,"name":...,
            # "arguments":...} cho mỗi lời gọi.
            for tc in m.get("tool_calls") or []:
                input_items.append({
                    "type": "function_call",
                    "call_id": tc.get("id", ""),
                    "name": tc["function"]["name"],
                    "arguments": tc["function"].get("arguments") or "{}",
                })
            continue

        # user
        content_val = m.get("content", "")
        if isinstance(content_val, list):
            input_items.append({
                "role": "user",
                "content": _convert_content_blocks_to_responses(content_val),
            })
        else:
            input_items.append({
                "role": "user",
                "content": content_val,
            })

    out: dict = {
        "model":  payload.get("model", ""),
        "input":  input_items,
        "stream": payload.get("stream", True),
    }

    if instructions_parts:
        out["instructions"] = "\n\n".join(instructions_parts)

    max_tok = payload.get("max_tokens")
    if max_tok is not None:
        out["max_output_tokens"] = max_tok

    temp = payload.get("temperature")
    if temp is not None:
        out["temperature"] = temp

    # Reasoning (/mode on|off) — field "thinking" được _apply_thinking_param()
    # (09_api_system.py) gắn sẵn theo schema trung gian OpenAI-shape
    # {"type": "enabled"|"disabled", ...} khi user bật /mode VÀ model này đã
    # xác nhận support (cache _thinking_support_get). Mỗi adapter tự dịch
    # tiếp sang schema thật của mình — Anthropic dùng "thinking":{type,
    # budget_tokens} (xem 01c_anthropic.py), Responses API dùng field HOÀN
    # TOÀN KHÁC: "reasoning": {"effort": low|medium|high|xhigh|none,
    # "summary": auto|concise|detailed} — xác nhận qua docs thật
    # (developers.openai.com/api/docs/guides/reasoning, mục ví dụ curl có
    # "reasoning": {"effort": "medium"}).
    #
    # on  → effort="medium" (mức cân bằng, KHÔNG suy ra từ budget_tokens
    #       của Anthropic vì 2 hệ đo hoàn toàn khác nhau — token count vs
    #       effort level rời rạc, không có công thức quy đổi chuẩn nào).
    #       summary="auto" là điều kiện BẮT BUỘC để server trả text đọc
    #       được (response.reasoning_summary_text.delta) — thiếu field này,
    #       response KHÔNG bao giờ có event reasoning nào cả (đã xác nhận
    #       qua nhiều nguồn: OpenAI reasoning guide + cookbook "we don't
    #       expose raw reasoning tokens, use summary parameter"), không
    #       phải lỗi — chỉ là bị câm lặng hoàn toàn không rõ nguyên nhân
    #       nếu thiếu bước dịch này.
    # off → effort="none" — đây là field CHUẨN để tắt reasoning theo docs,
    #       KHÁC hẳn "disabled" của Anthropic. Không có "summary" khi off
    #       (không có gì để tóm tắt).
    #
    # KHÔNG làm: "include": ["reasoning.encrypted_content"] và replay item
    # "reasoning" nhiều lượt — đó là tính năng giữ context reasoning qua
    # nhiều turn (stateless/ZDR), nằm ngoài yêu cầu "xử lý mode on/off",
    # cần thiết kế lưu trữ riêng (giống thinking_block của Anthropic) nếu
    # làm sau này.
    thinking = payload.get("thinking")
    if thinking and thinking.get("type") == "enabled":
        out["reasoning"] = {"effort": "medium", "summary": "auto"}
    elif thinking and thinking.get("type") == "disabled":
        out["reasoning"] = {"effort": "none"}

    # Tools: bỏ wrapper {"type":"function","function":{...}} (Chat-style,
    # "externally tagged") → field phẳng ở top-level (Responses style,
    # "internally tagged") — đúng 2 khác biệt nêu trong migrate guide mục
    # "Update function definitions".
    tools = payload.get("tools")
    if tools:
        out["tools"] = [
            {
                "type":        "function",
                "name":        t["function"]["name"],
                "description": t["function"].get("description", ""),
                "parameters":  t["function"].get("parameters", {}),
            }
            for t in tools if t.get("type") == "function"
        ]
        tc = payload.get("tool_choice", "auto")
        if tc == "required":
            out["tool_choice"] = "required"
        elif isinstance(tc, dict):
            out["tool_choice"] = {
                "type": "function",
                "name": tc.get("function", {}).get("name", ""),
            }
        else:
            out["tool_choice"] = "auto"

    return out


# ── Response stream: Responses SSE → giả lập SSE OpenAI Chat-style ──────────
def wrap_openai_responses_stream(raw_resp) -> "_ResponsesSSEResponse":
    """
    Bọc response Responses API streaming thành object iterable sinh ra đúng
    chuỗi b'data: {...}' theo schema Chat-Completions mà _stream_response()
    trong 09_api_system.py parse — để hàm đó không cần sửa 1 dòng nào (cùng
    pattern wrap_anthropic_stream()).
    """
    return _ResponsesSSEResponse(raw_resp)


class _ResponsesSSEResponse:
    """
    Responses API dùng SSE thật nhưng event schema khác Chat Completions.

    Các event đã xác nhận qua sample thật (function-calling guide, mục
    "Streaming function calls") + streaming-responses guide (text events)
    + reasoning guide (reasoning summary events):
      response.created              — bỏ qua (không cần map)
      response.output_text.delta    — {delta: "<text>"} → content
      response.reasoning_summary_text.delta
                                     — {delta: "<text>"} → field trung gian
                                        "thinking" (chỉ có khi request gửi
                                        "reasoning.summary", xem
                                        _to_responses_payload() /mode on)
      response.output_item.added    — {output_index, item:{type,
                                        "function_call"→id,call_id,name,
                                        arguments:""}} → khởi tạo 1 tool_call
      response.function_call_arguments.delta
                                     — {item_id, output_index, delta:"<...>"}
                                        → nối vào arguments của tool_call
      response.function_call_arguments.done
                                     — kết thúc 1 tool_call, không cần emit
                                        thêm gì (đã emit hết qua delta ở trên)
      response.completed            — kết thúc response, có usage
      error                          — lỗi

    Dịch sang OpenAI Chat-Completions chunk schema mà _stream_response()
    đọc: {choices: [{delta: {content|thinking|tool_calls}, finish_reason}],
    usage: {...}}.
    """

    def __init__(self, raw_resp):
        self._raw   = raw_resp
        self._lines = []    # hàng đợi SSE lines đã dịch
        self._buf   = b""
        self._done  = False
        # state theo dõi tool_call: output_index → {tc_idx, id, name}
        self._tool_blocks: dict[int, dict] = {}
        self._next_tc_idx = 0

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        while not self._lines:
            if self._done:
                raise StopIteration
            line = self._read_line()
            if line is None:
                self._done = True
                self._lines.append(b"data: [DONE]")
                continue
            self._process_line(line)
        return self._lines.pop(0)

    def _read_line(self) -> bytes | None:
        """Đọc 1 dòng SSE từ raw response. None nếu hết."""
        while b"\n" not in self._buf:
            chunk = self._raw.read(4096)
            if not chunk:
                return None
            self._buf += chunk
        idx = self._buf.index(b"\n")
        line, self._buf = self._buf[:idx], self._buf[idx + 1:]
        return line.rstrip(b"\r")

    def _emit(self, chunk: dict):
        self._lines.append(("data: " + json.dumps(chunk)).encode())

    def _process_line(self, line: bytes):
        """Parse 1 dòng SSE Responses API, dịch sang OpenAI Chat chunks."""
        text = line.decode("utf-8", errors="replace").strip()

        if text.startswith("event:"):
            return
        if not text.startswith("data:"):
            return

        ds = text[5:].strip()
        if not ds or ds == "[DONE]":
            self._done = True
            self._lines.append(b"data: [DONE]")
            return

        try:
            ev = json.loads(ds)
        except Exception:
            return

        etype = ev.get("type", "")

        if etype == "error":
            detail = ev.get("message") or json.dumps(ev, ensure_ascii=False)
            raise RuntimeError(f"OpenAI Responses stream error: {detail}")

        elif etype == "response.output_text.delta":
            delta_text = ev.get("delta", "")
            if delta_text:
                self._emit({"choices": [{"delta": {"content": delta_text}}]})

        elif etype == "response.reasoning_summary_text.delta":
            # Reasoning summary (KHÔNG phải raw chain-of-thought — OpenAI
            # không expose raw reasoning tokens qua API, chỉ có bản tóm tắt
            # do model tự viết lại khi request có "reasoning.summary" —
            # xem _to_responses_payload(). Field "delta" ở đây là text đọc
            # được, xác nhận qua sample event thật trong docs
            # (developers.openai.com/api/docs/api-reference/responses-streaming).
            # Emit qua field trung gian "thinking" (KHÔNG dùng "content")
            # — CÙNG QUY ƯỚC với 01c_anthropic.py (thinking_delta) để
            # _stream_response() (09_api_system.py) xử lý [thinking] tag,
            # thinking_parts, và cảnh báo leak-khi-off dùng chung 1 đường
            # code, không cần sửa gì thêm ở 09_api_system.py.
            delta_text = ev.get("delta", "")
            if delta_text:
                self._emit({"choices": [{"delta": {"thinking": delta_text}}]})

        elif etype == "response.output_item.added":
            item = ev.get("item", {})
            if item.get("type") == "function_call":
                idx = ev.get("output_index", 0)
                tc_idx = self._next_tc_idx
                self._next_tc_idx += 1
                self._tool_blocks[idx] = {
                    "tc_idx": tc_idx,
                    "call_id": item.get("call_id", ""),
                    "name": item.get("name", ""),
                }
                self._emit({"choices": [{"delta": {"tool_calls": [{
                    "index":    tc_idx,
                    "id":       item.get("call_id", ""),
                    "type":     "function",
                    "function": {"name": item.get("name", ""), "arguments": ""},
                }]}}]})

        elif etype == "response.function_call_arguments.delta":
            idx = ev.get("output_index", 0)
            tb = self._tool_blocks.get(idx)
            if tb is not None:
                self._emit({"choices": [{"delta": {"tool_calls": [{
                    "index":    tb["tc_idx"],
                    "function": {"arguments": ev.get("delta", "")},
                }]}}]})
            elif _cache_debug:
                # Orphan delta (chưa có output_item.added cho index này) —
                # cùng pattern log-khi-debug như 2 adapter kia, không đổi
                # hành vi mặc định (xem bug #3 ở 01c_anthropic.py).
                _cache_log("?", f"responses-sse idx={idx}",
                           "function_call_arguments.delta orphan (không có output_item.added) — bị bỏ qua")

        elif etype == "response.completed":
            resp = ev.get("response", {})
            usage = resp.get("usage", {})
            # finish_reason: Responses API không có field "stop_reason" như
            # Anthropic — trạng thái nằm ở response.status ("completed") và
            # việc có tool_call hay không suy ra từ output items đã emit
            # qua output_item.added ở trên. Nếu đã có bất kỳ tool_blocks nào
            # được ghi nhận trong response này → finish_reason="tool_calls",
            # ngược lại "stop" (đúng quy ước finish_reason của Chat
            # Completions mà _stream_response() đang đọc).
            finish = "tool_calls" if self._tool_blocks else "stop"
            self._emit({"choices": [{"delta": {}, "finish_reason": finish}]})
            if usage:
                in_tok  = usage.get("input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)
                self._emit({"usage": {
                    "prompt_tokens":     in_tok,
                    "completion_tokens": out_tok,
                    "total_tokens":      usage.get("total_tokens", in_tok + out_tok),
                }})
            self._done = True
            self._lines.append(b"data: [DONE]")

        # response.created / response.in_progress / response.output_item.done /
        # response.function_call_arguments.done / response.content_part.* —
        # không cần map, bỏ qua an toàn (không ảnh hưởng logic đọc của
        # _stream_response(), vốn chỉ cần content/tool_calls/finish_reason/usage).


# ── Response non-stream: dùng cho _call_simple() (compact history, giống
# parse_converse_response() ở 01b_aws.py) ──────────────────────────────────
def parse_responses_response(body: dict) -> dict:
    """
    Dịch response non-stream của Responses API (GET .../responses/{id} hoặc
    POST không stream) thành format {"text", "tool_calls"} mà code cũ đang
    trả về cho mọi provider khác — đọc từ body["output"] (list Items), theo
    đúng cấu trúc đã xác nhận ở migrate guide + function-calling guide.

    Không trả field reasoning riêng — hàm này chỉ dùng cho _call_simple()/
    _sub_urlopen() (text-only tasks: compact, rename, commit, review,
    subagent), không cần hiện [thinking] ra màn hình như turn chính (đó là
    việc của wrap_openai_responses_stream(), dùng cho call_api_stream()).
    """
    text = ""
    tool_calls = []
    has_reasoning_summary = False
    for item in body.get("output", []):
        itype = item.get("type")
        if itype == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text += c.get("text", "")
        elif itype == "function_call":
            tool_calls.append({
                "id": item.get("call_id", ""),
                "type": "function",
                "function": {
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments") or "{}",
                },
            })
        elif itype == "reasoning":
            # item type "reasoning" — {"id", "summary": [{"type":
            # "summary_text", "text":...}], "encrypted_content"?} — xác
            # nhận qua openai-python response_reasoning_item_param.py.
            # Chỉ cần biết CÓ summary hay không (dùng cho _probe_thinking_support
            # ở 09_api_system.py để xác định model có support reasoning
            # summary thật không), không cần nội dung text ở đây.
            if item.get("summary"):
                has_reasoning_summary = True
    return {"text": text, "tool_calls": tool_calls,
            "has_reasoning_summary": has_reasoning_summary}


# ── Models list ──────────────────────────────────────────────────────────────
def parse_openai_responses_models(data: dict) -> list[str]:
    """
    Parse response GET /models — Responses API dùng CHUNG endpoint /models
    với Chat Completions (cùng 1 tài khoản OpenAI, model list không đổi
    theo API dùng để gọi). Format: {"data": [{"id": "gpt-...", ...}]} —
    giống hệt chuẩn OpenAI-compat, chỉ tách hàm riêng để nhất quán với 2
    adapter kia (mỗi adapter tự có parse_models của mình) và để custom
    provider wizard gán đúng theo format đã chọn.
    """
    return [
        m["id"] for m in data.get("data", [])
        if m.get("id") and not any(x in m["id"].lower() for x in (
            "embed", "moderation", "tts", "whisper", "dall-e", "rerank",
        ))
    ]


# ── /end OPENAI RESPONSES ADAPTER ────────────────────────────────────────────
