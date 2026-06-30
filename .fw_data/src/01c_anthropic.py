# ##== ANTHROPIC MESSAGES API ADAPTER ==##
# Module độc lập — xử lý toàn bộ phần riêng của Anthropic Messages API
# (format request/response 2 chiều, SSE streaming khác OpenAI).
#
# THIẾT KẾ: đây là "chỗ chuyển". Code cũ (02_provider.py, 09_api_system.py)
# KHÔNG đổi gì — chỉ rẽ nhánh "if provider._format == 'anthropic': gọi vào
# đây" tại đúng vài điểm. Mọi thứ khác biệt của Anthropic (request/response
# schema khác OpenAI, SSE event name khác) được giả lập/dịch lại bên trong
# module này để phía gọi không cần biết.
#
# Hỗ trợ: custom provider thêm qua wizard với format_anthropic=True.
# Ví dụ: Requesty AI, CommandCode, hay endpoint self-hosted dùng Anthropic SDK.
#
# API docs: https://docs.anthropic.com/en/api/messages


ANTHROPIC_DEFAULT_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_MAX_TOKENS = 32768


# ── Request builder ──────────────────────────────────────────────────────────
def build_anthropic_request(path: str, api_key: str, payload: dict | None,
                             extra_headers: dict | None = None,
                             base_url: str = "https://api.anthropic.com/v1",
                             anthropic_version: str = ANTHROPIC_DEFAULT_VERSION,
                             auth_mode: str = "x-api-key",
                             ) -> "urllib.request.Request":
    """
    Tạo urllib.request.Request cho Anthropic Messages API.
    payload là OpenAI-style từ call_api_stream() — dịch sang Anthropic format.
    path: "/messages" hoặc "/v1/models" (GET để list models).

    auth_mode: "x-api-key" (default, đúng chuẩn Anthropic) hoặc "bearer"
    (một số gateway custom như OpenModel.ai bắt buộc Authorization: Bearer
    ở endpoint /models dù /messages chấp nhận cả hai — xem fetch_models()
    và get_api_key() trong 09_api_system.py, nơi auth_mode="bearer" được
    dùng làm fallback khi "x-api-key" trả 401).
    """
    url = path if path.startswith("http") else f"{base_url.rstrip('/')}{path}"

    if auth_mode == "bearer":
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        headers = {"x-api-key": api_key}
    headers["anthropic-version"] = anthropic_version
    headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(_to_anthropic_payload(payload)).encode()
        method = "POST"

    return urllib.request.Request(url, data=body, headers=headers, method=method)


# ── Payload convert: OpenAI-style → Anthropic Messages ──────────────────────
def _to_anthropic_payload(payload: dict) -> dict:
    """
    Dịch payload OpenAI-compat (messages, tools, tool_choice, max_tokens,
    stream, temperature...) mà call_api_stream() build sẵn,
    sang format Anthropic Messages API.
    """
    messages_in = payload.get("messages", [])
    system_parts: list[str] = []
    anth_messages: list[dict] = []

    # Gom liên tiếp các tool result (role=tool) vào 1 message user duy nhất
    # vì Anthropic yêu cầu tool_result phải nằm cùng 1 content list của user.
    pending_tool_results: list[dict] = []

    def _flush_tools():
        if pending_tool_results:
            anth_messages.append({
                "role": "user",
                "content": list(pending_tool_results),
            })
            pending_tool_results.clear()

    for m in messages_in:
        role = m.get("role")

        if role == "system":
            system_parts.append(m.get("content", ""))
            continue

        if role == "tool":
            # Tool result — gom vào pending. KHÔNG flush ở đây: nhiều
            # tool_result liên tiếp (tool song song trong cùng 1 turn) phải
            # nằm trong CÙNG 1 message user, đúng yêu cầu của Anthropic.
            # _flush_tools() chỉ được gọi khi gặp message KHÁC role=tool
            # (xem dòng dưới, trước khi xử lý user/assistant) — đó là lúc
            # thực sự có "msg khác xen giữa".
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": m.get("content", ""),
            })
            continue

        # Flush pending tool results trước khi xử lý msg mới (user/assistant)
        _flush_tools()

        if role == "assistant":
            content: list[dict] = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    # arguments thật sự malformed (vd model bị cắt stream giữa
                    # chừng) — fallback {} là hợp lý, không chặn cả turn.
                    # CHỈ bắt JSONDecodeError ở đây: bắt Exception rộng trước
                    # đây sẽ nuốt luôn KeyError/TypeError/NameError... từ lỗi
                    # code thật, biến chúng thành "input rỗng" âm thầm thay vì
                    # lộ ra để debug.
                    args = {}
                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": tc["function"]["name"],
                    "input": args,
                })
            # content rỗng CHỈ khi không có text VÀ không có tool_calls —
            # khi đó fallback 1 text block rỗng vì Anthropic cần ≥1 block.
            # Nếu có tool_use, content đã không rỗng → không bị fallback.
            # Replay thinking/redacted_thinking THẬT: nếu message gốc có
            # tool_calls VÀ thinking_block hợp lệ (lưu bởi agent_turn() ở
            # 09_api_system.py), prepend đúng block vào ĐẦU content —
            # Anthropic yêu cầu: "final assistant message must start with
            # a thinking (or redacted_thinking) block" khi nó dẫn tới
            # tool_use. Phải giữ nguyên văn, không sửa — kể cả với
            # redacted_thinking, dù "data" không đọc được, Anthropic vẫn
            # coi sửa đổi field này là lỗi 400 (docs: "you should pass
            # redacted_thinking blocks back to the API unchanged").
            tb = m.get("thinking_block")
            if m.get("tool_calls") and isinstance(tb, dict):
                if tb.get("redacted"):
                    content.insert(0, {
                        "type": "redacted_thinking",
                        "data": tb["redacted"],
                    })
                elif tb.get("signature"):
                    content.insert(0, {
                        "type":      "thinking",
                        "thinking":  tb.get("thinking", ""),
                        "signature": tb.get("signature", ""),
                    })
            anth_messages.append({"role": "assistant", "content": content or [{"type": "text", "text": ""}]})

        else:  # user
            content_val = m.get("content", "")
            anth_messages.append({
                "role": "user",
                "content": content_val if isinstance(content_val, list) else [{"type": "text", "text": content_val}],
            })

    _flush_tools()  # flush cuối nếu message cuối là tool result

    out: dict = {
        "model":      payload.get("model", ""),
        "max_tokens": payload.get("max_tokens", ANTHROPIC_DEFAULT_MAX_TOKENS),
        "messages":   anth_messages,
        "stream":     payload.get("stream", True),
    }

    if system_parts:
        out["system"] = "\n\n".join(system_parts)

    temp = payload.get("temperature")
    if temp is not None:
        out["temperature"] = temp

    # Extended thinking — field "thinking" được _apply_thinking_param()
    # (09_api_system.py) gắn sẵn theo OpenAI-shape payload khi user bật
    # /mode thinking VÀ provider+model này đã xác nhận support (cache).
    # Dịch sang đúng format Anthropic Messages API:
    #   https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
    #
    # Lưu/replay thinking THẬT: agent_turn() (09_api_system.py) lưu
    # a_msg["thinking_block"] = {"thinking":..., "signature":...} (block
    # thường) HOẶC {"redacted": ...} (redacted_thinking, khi nội dung suy
    # luận bị hệ thống an toàn của Anthropic mã hoá — không có "thinking
    # text" đọc được, chỉ có "data" opaque, xem nhánh redacted_thinking ở
    # _to_anthropic_payload bên trên) khi turn đó có tool_calls. Ở đây,
    # nếu message assistant gần nhất (có thể không phải message cuối cùng
    # trong list — turn sau nó có thể đã .extend() thêm tool result) có
    # tool_calls VÀ có thinking_block hợp lệ (1 trong 2 dạng trên), giữ
    # nguyên thinking cho turn này — phần prepend thật sự nằm ở vòng lặp
    # build content phía trên (Anthropic yêu cầu: "final assistant message
    # must start with a thinking or redacted_thinking block"). Nếu KHÔNG
    # có thinking_block hợp lệ (history cũ trước khi có fix này, hoặc
    # provider không trả về signature/redacted) → tự động tắt thinking cho
    # turn này thay vì cố gửi rồi ăn lỗi 400.
    thinking = payload.get("thinking")
    if thinking and thinking.get("type") == "enabled":
        _last_assistant = next(
            (m for m in reversed(messages_in) if m.get("role") == "assistant"),
            None,
        )
        if _last_assistant and _last_assistant.get("tool_calls"):
            tb = _last_assistant.get("thinking_block")
            _has_valid_tb = isinstance(tb, dict) and (
                tb.get("redacted") or tb.get("signature")
            )
            if not _has_valid_tb:
                thinking = None  # thiếu thinking_block hợp lệ — bỏ qua, không set out["thinking"]
    if thinking and thinking.get("type") == "enabled":
        budget = thinking.get("budget_tokens", 8000)
        out["thinking"] = {"type": "enabled", "budget_tokens": budget}
        # Anthropic KHÔNG cho phép set temperature khi thinking bật (API
        # trả 400 nếu có) — bỏ field này, không liên quan gì tới việc
        # _no_temperature() đã xử lý cho Claude 4+ ở trên, đây là rule
        # riêng của thinking mode, áp dụng bất kể model nào.
        out.pop("temperature", None)
        # max_tokens phải LỚN HƠN budget_tokens, nếu không Anthropic 400.
        if out.get("max_tokens", 0) <= budget:
            out["max_tokens"] = budget + ANTHROPIC_DEFAULT_MAX_TOKENS
    elif thinking is not None and thinking.get("type") == "disabled":
        # Trước đây nhánh này là code chết — "disabled" không bao giờ được
        # set vào request thật. Vô hại với Anthropic gốc (mặc định tắt
        # sẵn) nhưng rủi ro thật với custom provider format_anthropic=True
        # tự bật thinking mặc định phía server (vd gateway dựa trên
        # DeepSeek-shape). Set tường minh để /mode off tắt được thật.
        out["thinking"] = {"type": "disabled"}

    out["messages"] = anth_messages

    # Tools
    tools = payload.get("tools")
    if tools:
        out["tools"] = [
            {
                "name":         t["function"]["name"],
                "description":  t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {}),
            }
            for t in tools if t.get("type") == "function"
        ]
        tc = payload.get("tool_choice", "auto")
        if tc == "required":
            out["tool_choice"] = {"type": "any"}
        elif isinstance(tc, dict):
            out["tool_choice"] = {"type": "tool", "name": tc.get("function", {}).get("name", "")}
        else:
            out["tool_choice"] = {"type": "auto"}

    # Defensive: bỏ các key OpenAI-specific nếu có lọt vào out
    # (out được build mới từ đầu nên thực tế 2 key này chưa bao giờ tồn tại
    #  trong out — pop là no-op, giữ lại như guard phòng trường hợp code
    #  upstream thay đổi sau này)
    for drop_key in ("parallel_tool_calls", "stream_options"):
        out.pop(drop_key, None)

    return out


# ── Response stream: Anthropic SSE → giả lập SSE OpenAI-style ───────────────
def wrap_anthropic_stream(raw_resp) -> "_AnthropicSSEResponse":
    """
    Bọc response Anthropic streaming thành object iterable sinh ra
    đúng chuỗi b'data: {...}' theo schema OpenAI mà _stream_response()
    trong 09_api_system.py parse — để hàm đó không cần sửa 1 dòng nào.
    """
    return _AnthropicSSEResponse(raw_resp)


class _AnthropicSSEResponse:
    """
    Anthropic streaming dùng SSE thật nhưng event name khác OpenAI.

    Các event Anthropic:
      message_start         — {message: {usage: {input_tokens, ...}}}
      content_block_start   — {index, content_block: {type, id, name, ...}}
      content_block_delta   — {index, delta: {type, text|partial_json}}
      content_block_stop    — {index}
      message_delta         — {delta: {stop_reason}, usage: {output_tokens}}
      message_stop          — kết thúc

    Dịch sang OpenAI chunk schema mà _stream_response() đọc:
      {choices: [{delta: {content|tool_calls}, finish_reason}], usage: {...}}
    """

    def __init__(self, raw_resp):
        self._raw     = raw_resp
        self._lines   = []    # hàng đợi SSE lines đã dịch
        self._buf     = b""
        self._done    = False
        # state theo dõi tool_use block: index → {tc_idx, id, name}
        self._tool_blocks: dict[int, dict] = {}
        self._next_tc_idx = 0
        # input_tokens nhận từ message_start — phải giữ lại và gộp vào
        # chunk usage cuối (message_delta), KHÔNG emit riêng. Lý do: phía
        # _stream_response() (09_api_system.py) dùng usage_out.update() —
        # nếu emit 2 chunk usage riêng (input rồi output), update() lần 2
        # sẽ ĐÈ MẤT prompt_tokens vì chunk output không có field đó.
        self._prompt_tokens = 0

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
        """Parse 1 dòng SSE Anthropic, dịch sang OpenAI chunks."""
        text = line.decode("utf-8", errors="replace").strip()

        # Bỏ qua dòng event: ... (chỉ cần data:)
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
            err = ev.get("error") or {}
            detail = err.get("message") or json.dumps(err, ensure_ascii=False)
            raise RuntimeError(
                f"Anthropic stream error ({err.get('type', 'unknown')}): {detail}")

        if etype == "message_start":
            # Lưu lại input_tokens — KHÔNG emit usage riêng ở đây (xem lý do
            # ở __init__). Sẽ gộp vào chunk usage cuối ở message_delta.
            usage = ev.get("message", {}).get("usage", {})
            if usage:
                self._prompt_tokens = usage.get("input_tokens", 0)

        elif etype == "content_block_start":
            idx   = ev.get("index", 0)
            block = ev.get("content_block", {})
            btype = block.get("type", "")
            if btype == "tool_use":
                if idx in self._tool_blocks:
                    # FIX (bug #4): content_block_start lặp lại cùng index —
                    # vi phạm spec Anthropic (mỗi index chỉ start 1 lần),
                    # nhưng có tiền lệ thật với gateway third-party lệch
                    # spec (custom provider format_anthropic=True). Trước
                    # đây ghi đè vô điều kiện làm "mồ côi" tool_call cũ
                    # (mọi delta sau map nhầm sang tool mới). Giờ log cảnh
                    # báo nếu debug bật, rồi vẫn tiếp tục với index mới —
                    # không thay đổi hành vi observable trong trường hợp
                    # bình thường (Anthropic chính chủ không bao giờ lặp).
                    if _cache_debug:
                        _cache_log("?", f"anthropic-sse idx={idx}",
                                   "content_block_start lặp lại — tool_call cũ bị ghi đè")
                tc_idx = self._next_tc_idx
                self._next_tc_idx += 1
                self._tool_blocks[idx] = {
                    "tc_idx": tc_idx,
                    "id":     block.get("id", ""),
                    "name":   block.get("name", ""),
                }
                self._emit({"choices": [{"delta": {"tool_calls": [{
                    "index":    tc_idx,
                    "id":       block.get("id", ""),
                    "type":     "function",
                    "function": {"name": block.get("name", ""), "arguments": ""},
                }]}}]})
            elif btype == "redacted_thinking":
                # KHÁC thinking thường: redacted_thinking không stream qua
                # nhiều delta nhỏ — toàn bộ nội dung đã mã hoá nằm sẵn
                # trong field "data" ngay tại content_block_start (xem
                # docs.anthropic.com/en/docs/build-with-claude/extended-thinking,
                # mục "redacted_thinking"). Không có content_block_delta
                # nào theo sau cho block này (đi thẳng tới content_block_stop).
                # Emit nguyên block 1 lần qua field riêng "redacted_thinking_data"
                # — _stream_response() (09_api_system.py) gom field này
                # tương tự thinking_signature, không lẫn với "thinking"
                # (text đọc được) vì redacted KHÔNG có text đọc được.
                data = block.get("data", "")
                if data:
                    self._emit({"choices": [{"delta": {
                        "redacted_thinking_data": data}}]})
            # text block — không cần emit gì ở đây

        elif etype == "content_block_delta":
            idx   = ev.get("index", 0)
            delta = ev.get("delta", {})
            dtype = delta.get("type", "")
            if dtype == "text_delta":
                self._emit({"choices": [{"delta": {"content": delta.get("text", "")}}]})
            elif dtype == "input_json_delta":
                tb = self._tool_blocks.get(idx)
                if tb is not None:
                    self._emit({"choices": [{"delta": {"tool_calls": [{
                        "index":    tb["tc_idx"],
                        "function": {"arguments": delta.get("partial_json", "")},
                    }]}}]})
                elif _cache_debug:
                    # FIX (bug #3): trước đây orphan delta (content_block_delta
                    # đến cho 1 index chưa từng có content_block_start) bị vứt
                    # hoàn toàn, không dấu vết — hậu quả downstream là
                    # arguments rỗng, tool bị gọi thiếu tham số mà không rõ
                    # nguyên nhân gốc. Vi phạm spec Anthropic (chỉ xảy ra với
                    # gateway third-party lệch spec), nên chỉ log khi debug
                    # bật, không đổi hành vi mặc định.
                    _cache_log("?", f"anthropic-sse idx={idx}",
                               "input_json_delta orphan (không có content_block_start) — bị bỏ qua")
            elif dtype == "thinking_delta":
                # Extended thinking — text suy luận thật. Emit qua field
                # riêng "thinking" (KHÔNG dùng "content") để _stream_response()
                # (09_api_system.py) phân biệt được với text trả lời thường,
                # và không lẫn với "reasoning_content" (cơ chế riêng của
                # DeepSeek/OpenAI-shape) — 2 cơ chế tách biệt hoàn toàn.
                self._emit({"choices": [{"delta": {"thinking": delta.get("thinking", "")}}]})
            elif dtype == "signature_delta":
                # Chữ ký mã hoá thinking block — bắt buộc phải lưu nguyên
                # văn để replay đúng ở turn sau có tool_calls (Anthropic
                # docs: "we recommend passing everything back as you
                # received it"). Field riêng "thinking_signature".
                self._emit({"choices": [{"delta": {"thinking_signature": delta.get("signature", "")}}]})

        elif etype == "message_delta":
            delta  = ev.get("delta", {})
            usage  = ev.get("usage", {})
            reason_map = {
                "end_turn":      "stop",
                "tool_use":      "tool_calls",
                "max_tokens":    "length",
                "stop_sequence": "stop",
            }
            stop_reason = delta.get("stop_reason", "end_turn")
            finish      = reason_map.get(stop_reason, "stop")
            self._emit({"choices": [{"delta": {}, "finish_reason": finish}]})
            if usage:
                out_tok = usage.get("output_tokens", 0)
                self._emit({"usage": {
                    "prompt_tokens":     self._prompt_tokens,
                    "completion_tokens": out_tok,
                    "total_tokens":      self._prompt_tokens + out_tok,
                }})

        elif etype == "message_stop":
            self._done = True
            self._lines.append(b"data: [DONE]")


# ── Models list ──────────────────────────────────────────────────────────────
def parse_anthropic_models(data: dict) -> list[str]:
    """
    Parse response GET /v1/models từ Anthropic API.
    Format: {"data": [{"id": "claude-...", "type": "model", ...}]}
    Lọc chỉ giữ model chat (bỏ embed/moderation nếu có).
    """
    return [
        m["id"] for m in data.get("data", [])
        if m.get("id") and not any(x in m["id"].lower() for x in (
            "embed", "moderation",
        ))
    ]


# ── /end ANTHROPIC ADAPTER ───────────────────────────────────────────────────
