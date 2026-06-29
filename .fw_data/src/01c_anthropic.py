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
                except Exception:
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
