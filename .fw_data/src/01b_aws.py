# ##== AWS BEDROCK ADAPTER ==##
# Module độc lập — xử lý toàn bộ phần riêng của AWS Bedrock (Bedrock API Key
# auth, Converse/ConverseStream API, dịch format request/response 2 chiều).
#
# THIẾT KẾ: đây là "chỗ chuyển". Code cũ (02_provider.py, 09_api_system.py)
# KHÔNG đổi gì — chỉ rẽ nhánh "if _active_provider == 'aws_bedrock': gọi vào
# đây" tại đúng vài điểm. Mọi thứ khác biệt của Bedrock (request/response
# schema khác OpenAI, stream format khác SSE) được giả lập/dịch lại bên
# trong module này để phía gọi không cần biết.
#
# Auth: AWS Bedrock API Key (tạo trong Console → Bedrock → API keys) dùng
# trực tiếp như Bearer token — KHÔNG cần tự ký SigV4, AWS verify phía họ.
# Y hệt cách _provider_request() gốc đang gắn "Authorization: Bearer <key>"
# cho Fireworks/Mistral/... Khác biệt duy nhất: Bedrock cần biết region để
# build URL endpoint (bedrock-runtime.{region}.amazonaws.com), nên giá trị
# lưu vào config_key/env_key gộp dạng "{region}|{api_key}".
#
# Format chuỗi credentials: "us-east-1|bedrock-api-key-xxxx..." hoặc
#                            "us-east-1|ABSKQmVk..." (long-term key)

import struct as _struct   # parse AWS event-stream binary frame (xem _FakeSSEResponse)
import datetime as _dt     # timestamp cho cache model-cần-prefix (TTL 12h)


# ── Region picker (gọi từ get_api_key() khi nhập key lần đầu) ─────────────
# Chỉ liệt kê các region phổ biến có Bedrock — tránh bắt user tự gõ tay,
# dễ gõ sai/quên. Không cần đầy đủ mọi region AWS, chỉ cần đủ dùng.
BEDROCK_REGIONS = [
    "us-east-1",
    "us-west-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "eu-central-1",
    "eu-west-1",
]


def choose_region() -> str:
    """Hiện menu chọn region Bedrock (menu số, giống choose_provider/choose_model)."""
    print(f"\n{CYAN}{BOLD}AWS Bedrock{R}  {DIM}— chọn region{R}")
    for i, r in enumerate(BEDROCK_REGIONS, 1):
        print(f"  {YELLOW}{i}{R}  {WHITE}{r}{R}")
    while True:
        try:
            raw = input(f"  {CYAN}❯ {DIM}[1]{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{RED}Huỷ.{R}"); sys.exit(0)
        if not raw:
            return BEDROCK_REGIONS[0]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(BEDROCK_REGIONS):
                return BEDROCK_REGIONS[idx]
        except ValueError:
            pass
        print(f"  {RED}Số không hợp lệ (1–{len(BEDROCK_REGIONS)}).{R}")


# ── Geo prefix suy luận từ region (cho cross-region inference profile) ────
# AWS yêu cầu nhiều model (đa số Anthropic/Llama/Nova mới) phải gọi qua
# "inference profile" thay vì model ID trần — cách đơn giản nhất là thêm
# tiền tố geography (us./eu./apac.) vào trước model ID. Suy luận tiền tố
# từ region đang dùng theo đúng quy ước đặt tên AWS (us-*, eu-*, ap-*).
def _geo_prefix(region: str) -> str:
    if region.startswith("us-gov"):
        return "us-gov."
    if region.startswith("us"):
        return "us."
    if region.startswith("eu"):
        return "eu."
    if region.startswith("ap"):
        return "apac."
    return "us."   # fallback an toàn


# Nhớ model nào đã xác nhận cần prefix, để các lần gọi sau (trong cùng
# tiến trình HOẶC sau khi mở lại app) khỏi phải tốn 1 lượt gọi lỗi rồi
# mới retry. Lưu bền vững xuống config.json kèm timestamp, tự hết hạn
# sau PROFILE_CACHE_TTL_HOURS giờ — vì đây là suy luận (không phải AWS
# xác nhận chính thức), nên làm mới định kỳ để tránh sai lệch nếu AWS
# thay đổi chính sách phía họ.
PROFILE_CACHE_TTL_HOURS = 12
_PROFILE_REQUIRED_MODELS: set[str] = set()
_profile_cache_loaded = False


def _load_profile_cache():
    """
    Đọc config["aws_bedrock_profile_models"] = {model_id: iso_timestamp},
    nạp vào _PROFILE_REQUIRED_MODELS — bỏ qua (coi như hết hạn) entry cũ
    hơn PROFILE_CACHE_TTL_HOURS giờ. Chỉ chạy 1 lần mỗi tiến trình.
    """
    global _profile_cache_loaded
    if _profile_cache_loaded:
        return
    _profile_cache_loaded = True
    try:
        cfg = load_config()
        saved = cfg.get("aws_bedrock_profile_models", {})
        now = _dt.datetime.now(_dt.timezone.utc)
        still_valid = {}
        for model_id, ts_str in saved.items():
            try:
                ts = _dt.datetime.fromisoformat(ts_str)
                age_hours = (now - ts).total_seconds() / 3600
                if age_hours < PROFILE_CACHE_TTL_HOURS:
                    _PROFILE_REQUIRED_MODELS.add(model_id)
                    still_valid[model_id] = ts_str
            except Exception:
                continue   # entry hỏng — bỏ qua, không nạp
        # Nếu có entry bị loại do hết hạn, ghi lại file cho gọn (best-effort)
        if len(still_valid) != len(saved):
            try:
                cfg["aws_bedrock_profile_models"] = still_valid
                save_config(cfg)
            except Exception:
                pass
    except Exception:
        pass   # không có config hoặc lỗi đọc — coi như chưa biết model nào


def _remember_profile_required(model_id: str):
    """Đánh dấu model_id cần prefix, lưu cả vào RAM lẫn config.json (kèm timestamp)."""
    _PROFILE_REQUIRED_MODELS.add(model_id)
    try:
        cfg = load_config()
        saved = cfg.get("aws_bedrock_profile_models", {})
        saved[model_id] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        cfg["aws_bedrock_profile_models"] = saved
        save_config(cfg)
    except Exception:
        pass   # ghi lỗi (vd disk full) — không chặn luồng chính, vẫn dùng RAM


def urlopen_smart(req, raw_credentials: str, payload: dict, timeout: int = 180):
    """
    Wrapper quanh urllib.request.urlopen() dành riêng cho Bedrock: nếu
    request đầu tiên lỗi HTTP 400 với message "on-demand throughput isn't
    supported" (AWS yêu cầu inference profile cho model này), tự động
    build lại request với model ID có tiền tố geography (us./eu./apac.)
    rồi thử lại đúng 1 lần — để code gọi (call_api_stream) không cần biết
    gì về cơ chế inference profile của AWS.
    """
    _load_profile_cache()
    model_id = (payload or {}).get("model", "")

    # Nếu model này đã biết cần prefix từ lần trước (RAM hoặc đã nạp từ
    # config.json, còn hạn ≤12h) → áp dụng luôn, khỏi tốn 1 lượt gọi lỗi.
    if model_id in _PROFILE_REQUIRED_MODELS:
        req = _rebuild_with_prefixed_model(req, raw_credentials, payload)

    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if "on-demand throughput" not in body and "inference profile" not in body:
            raise   # lỗi 400 khác, không phải vấn đề inference profile

        # Đánh dấu để các lần gọi sau (cùng model, kể cả mở lại app trong
        # 12h tới) áp dụng prefix ngay từ đầu.
        _remember_profile_required(model_id)
        retry_req = _rebuild_with_prefixed_model(req, raw_credentials, payload)
        return urllib.request.urlopen(retry_req, timeout=timeout)


def _rebuild_with_prefixed_model(req, raw_credentials: str, payload: dict):
    """Build lại request với model ID có tiền tố geography (us./eu./apac.)."""
    cred = parse_credentials(raw_credentials)
    prefix = _geo_prefix(cred["region"])
    model_id = (payload or {}).get("model", "")
    if model_id.startswith(("us.", "eu.", "apac.", "jp.", "au.", "us-gov.", "global.")):
        return req   # đã có prefix sẵn rồi, không cần thêm nữa
    new_payload = {**payload, "model": prefix + model_id}
    op = "converse-stream" if new_payload.get("stream") else "converse"
    return build_request(op, raw_credentials, new_payload)


# ── Credentials ────────────────────────────────────────────────────────────
def parse_credentials(raw: str) -> dict:
    """
    Tách chuỗi "{region}|{api_key}" thành {region, api_key}.
    Raise ValueError với message rõ ràng nếu format sai.
    """
    if "|" not in raw:
        raise ValueError(
            "AWS Bedrock cần region + API key dạng 'region|api_key', vd:\n"
            "  us-east-1|bedrock-api-key-xxxxxxxx"
        )
    region, api_key = raw.split("|", 1)
    region  = region.strip() or "us-east-1"
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("AWS Bedrock API key trống — kiểm tra lại config.")
    return {"region": region, "api_key": api_key}


# ── Request builder (gọi từ _provider_request trong 02_provider.py) ───────
def build_request(path: str, raw_credentials: str, payload: dict | None,
                   extra_headers: dict | None = None) -> "urllib.request.Request":
    """
    Tạo urllib.request.Request với Bearer token Bedrock API Key, để code cũ
    chỉ cần urlopen(req) y như với các provider khác — không cần biết bên
    trong là Bedrock.

    `path` ở đây dùng làm chỉ dấu thao tác:
      - "converse"     → gọi Converse (non-streaming, op thật chọn theo
                          payload["stream"])
      - "list_models"  → gọi ListFoundationModels
    Việc build URL AWS thật (khác hẳn base_url OpenAI-style) xử lý hết ở
    đây, path truyền vào chỉ là cờ hiệu từ phía gọi cũ.
    """
    cred   = parse_credentials(raw_credentials)
    region = cred["region"]

    if path == "list_models":
        url    = f"https://bedrock.{region}.amazonaws.com/foundation-models"
        body   = b""
        method = "GET"
    else:
        model_id = (payload or {}).get("model", "")
        op = "converse-stream" if (payload or {}).get("stream") else "converse"
        url    = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/{op}"
        body   = json.dumps(_to_converse_payload(payload or {})).encode()
        method = "POST"

    headers = {
        "Authorization": f"Bearer {cred['api_key']}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    return urllib.request.Request(url, data=(body or None), headers=headers,
                                   method=method)


# ── Request payload: OpenAI-style → Converse-style ─────────────────────────
def _to_converse_payload(payload: dict) -> dict:
    """
    Dịch payload OpenAI-compat (messages, tools, tool_choice, max_tokens...)
    mà call_api_stream() build sẵn, sang format Converse API của Bedrock.
    """
    messages = payload.get("messages", [])
    system_blocks = []
    converse_messages = []

    # Gom consecutive role=tool vào 1 message user duy nhất.
    # Bedrock Converse yêu cầu tất cả toolResult liên tiếp nằm trong
    # 1 message user với nhiều toolResult blocks — không được tách thành
    # nhiều message user riêng lẻ (sẽ gây HTTP 400 "messages must alternate").
    # OpenAI-compat giữ chúng là nhiều message role=tool riêng → cần gom ở đây.
    # Thuật toán: buffer các tool message liên tiếp, flush thành 1 message
    # khi gặp message không phải tool.
    pending_tool_results: list = []

    def _flush_tool_results():
        if pending_tool_results:
            converse_messages.append({
                "role": "user",
                "content": list(pending_tool_results),
            })
            pending_tool_results.clear()

    for m in messages:
        role = m.get("role")
        if role == "system":
            _flush_tool_results()
            system_blocks.append({"text": m.get("content", "")})
            continue
        if role == "tool":
            # Buffer — chưa flush, chờ gom đủ các tool results liên tiếp
            pending_tool_results.append({
                "toolResult": {
                    "toolUseId": m.get("tool_call_id", ""),
                    "content": [{"text": m.get("content", "")}],
                }
            })
            continue

        # Gặp message không phải tool → flush buffer trước
        _flush_tool_results()
        content = []
        if m.get("content"):
            content.append({"text": m["content"]})
        for tc in m.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            content.append({
                "toolUse": {
                    "toolUseId": tc.get("id", ""),
                    "name": tc["function"]["name"],
                    "input": args,
                }
            })
        converse_messages.append({
            "role": "assistant" if role == "assistant" else "user",
            "content": content or [{"text": ""}],
        })

    # Flush tool results còn lại cuối list
    _flush_tool_results()

    out = {
        "messages": converse_messages,
        "inferenceConfig": {
            "maxTokens": payload.get("max_tokens", 4096),
            "temperature": payload.get("temperature", 0.3),
        },
    }
    if system_blocks:
        out["system"] = system_blocks

    tools = payload.get("tools")
    if tools:
        out["toolConfig"] = {
            "tools": [
                {
                    "toolSpec": {
                        "name": t["function"]["name"],
                        "description": t["function"].get("description", ""),
                        "inputSchema": {"json": t["function"].get("parameters", {})},
                    }
                }
                for t in tools if t.get("type") == "function"
            ]
        }
        tc = payload.get("tool_choice", "auto")
        if tc == "required":
            out["toolConfig"]["toolChoice"] = {"any": {}}
        elif isinstance(tc, dict):
            out["toolConfig"]["toolChoice"] = {
                "tool": {"name": tc.get("function", {}).get("name", "")}
            }
        else:
            out["toolConfig"]["toolChoice"] = {"auto": {}}

    return out


# ── Response stream: Bedrock event-stream → giả lập SSE OpenAI-style ──────
def wrap_stream_response(raw_resp) -> "_FakeSSEResponse":
    """
    Bọc response thật từ urlopen(Bedrock ConverseStream) thành 1 object
    iterable-theo-dòng, sinh ra đúng chuỗi 'data: {...}\\n\\n' theo schema
    OpenAI mà _stream_response() trong 09_api_system.py đang parse —
    để hàm đó không cần sửa 1 dòng nào.
    """
    return _FakeSSEResponse(raw_resp)


class _FakeSSEResponse:
    """
    Giả lập object response mà `for raw_line in resp` (trong
    _stream_response) đọc được — mỗi __next__ trả về 1 dòng bytes dạng
    b'data: {...}' đúng format OpenAI streaming delta.

    Bedrock event-stream thật dùng AWS "vnd.amazon.eventstream" binary
    framing (spec: https://smithy.io/2.0/aws/amazon-eventstream.html).
    Mỗi message gồm:
      prelude: uint32 total_length, uint32 headers_length, uint32 prelude_crc
      headers: key-value pairs (tên loại event nằm ở header ":event-type")
      payload: JSON — nội dung CỦA RIÊNG event đó, KHÔNG bọc thêm key
               ngoài (vd payload của event contentBlockDelta là thẳng
               {"contentBlockIndex":0,"delta":{...}}, loại event đọc từ
               header ":event-type", không phải từ key JSON).
      message_crc: uint32

    _read_one_event() bóc đúng frame theo spec trên (prelude 12 byte, có
    đọc header thật để lấy event-type), _convert_event() dịch sang chunk
    JSON kiểu OpenAI.
    """

    def __init__(self, raw_resp):
        self._raw = raw_resp
        self._buf = b""
        self._lines = []   # hàng đợi các dòng SSE đã dịch, chờ trả ra
        self._tool_block_idx = {}   # contentBlockIndex(Bedrock) -> tc index OpenAI
        self._next_tc_idx = 0
        self._done = False

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        while not self._lines:
            if self._done:
                raise StopIteration
            parsed = self._read_one_event()
            if parsed is None:
                self._done = True
                self._lines.append(b"data: [DONE]")
                continue
            event_type, payload = parsed
            for chunk in _convert_event(event_type, payload,
                                         self._tool_block_idx, self):
                self._lines.append(
                    ("data: " + json.dumps(chunk)).encode())
        return self._lines.pop(0)

    # -- đọc đúng 1 frame event-stream theo spec AWS, trả về (event_type, payload_dict)
    def _read_one_event(self) -> tuple[str, dict] | None:
        prelude = self._read_exact(12)   # total_length + headers_length + prelude_crc
        if prelude is None:
            return None
        total_len, headers_len, _prelude_crc = _struct.unpack(">III", prelude)
        # rest = headers + payload + message_crc(4) — đã trừ 12 byte prelude
        rest = self._read_exact(total_len - 12)
        if rest is None:
            return None
        headers_raw = rest[:headers_len]
        payload_raw = rest[headers_len:-4]   # bỏ 4 byte message_crc ở cuối
        headers = _parse_eventstream_headers(headers_raw)
        event_type = headers.get(":event-type", "")
        message_type = headers.get(":message-type", "event")
        if message_type in ("error", "exception"):
            # Lỗi từ AWS giữa luồng (vd throttling, validation) — dừng
            # luồng, không cố parse payload như event bình thường.
            return None
        try:
            payload = json.loads(payload_raw.decode("utf-8")) if payload_raw else {}
        except Exception:
            payload = {}
        return (event_type, payload)

    def _read_exact(self, n: int) -> bytes | None:
        while len(self._buf) < n:
            chunk = self._raw.read(4096)
            if not chunk:
                return None
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out


def _parse_eventstream_headers(raw: bytes) -> dict:
    """
    Parse phần headers của 1 frame event-stream theo spec AWS:
    mỗi header = [1 byte name_len][name][1 byte type][value theo type].
    Chỉ cần đọc đúng để lấy ":event-type" (string) — nhưng phải parse
    đúng MỌI header để không bị lệch offset cho header tiếp theo, kể cả
    loại không dùng tới.
    """
    headers = {}
    i = 0
    n = len(raw)
    while i < n:
        name_len = raw[i]; i += 1
        name = raw[i:i+name_len].decode("utf-8"); i += name_len
        type_id = raw[i]; i += 1
        if type_id in (0, 1):          # bool true/false — không có value byte
            value = (type_id == 0)
        elif type_id == 2:             # byte
            value = _struct.unpack(">b", raw[i:i+1])[0]; i += 1
        elif type_id == 3:             # short
            value = _struct.unpack(">h", raw[i:i+2])[0]; i += 2
        elif type_id == 4:             # integer
            value = _struct.unpack(">i", raw[i:i+4])[0]; i += 4
        elif type_id == 5:             # long
            value = _struct.unpack(">q", raw[i:i+8])[0]; i += 8
        elif type_id == 6:             # byte_array — 2-byte len prefix
            vlen = _struct.unpack(">H", raw[i:i+2])[0]; i += 2
            value = raw[i:i+vlen]; i += vlen
        elif type_id == 7:             # string — 2-byte len prefix
            vlen = _struct.unpack(">H", raw[i:i+2])[0]; i += 2
            value = raw[i:i+vlen].decode("utf-8"); i += vlen
        elif type_id == 8:             # timestamp — 8-byte ms epoch
            value = _struct.unpack(">q", raw[i:i+8])[0]; i += 8
        elif type_id == 9:             # uuid — 16 byte
            value = raw[i:i+16]; i += 16
        else:
            break   # type lạ không rõ — dừng parse để tránh đọc lệch
        headers[name] = value
    return headers


def _convert_event(event_type: str, payload: dict, tool_block_idx: dict,
                    state: "_FakeSSEResponse") -> list[dict]:
    """
    Dịch 1 event Bedrock Converse Stream (đã biết event_type từ header,
    payload là nội dung trực tiếp của event đó) sang 0..n "chunk" JSON
    kiểu OpenAI chat.completion.chunk — đúng schema mà _stream_response()
    đọc qua chunk["choices"][0]["delta"].
    """
    out = []

    if event_type == "contentBlockStart":
        idx   = payload.get("contentBlockIndex", 0)
        start = payload.get("start", {})
        if "toolUse" in start:
            tu = start["toolUse"]
            tc_idx = state._next_tc_idx
            state._next_tc_idx += 1
            tool_block_idx[idx] = tc_idx
            out.append({"choices": [{"delta": {"tool_calls": [{
                "index": tc_idx,
                "id": tu.get("toolUseId", ""),
                "function": {"name": tu.get("name", ""), "arguments": ""},
            }]}}]})

    elif event_type == "contentBlockDelta":
        idx   = payload.get("contentBlockIndex", 0)
        delta = payload.get("delta", {})
        if "text" in delta:
            out.append({"choices": [{"delta": {"content": delta["text"]}}]})
        elif "toolUse" in delta:
            tc_idx = tool_block_idx.get(idx, 0)
            partial = delta["toolUse"].get("input", "")
            out.append({"choices": [{"delta": {"tool_calls": [{
                "index": tc_idx,
                "function": {"arguments": partial},
            }]}}]})

    elif event_type == "messageStop":
        reason_map = {
            "end_turn": "stop", "tool_use": "tool_calls",
            "max_tokens": "length", "stop_sequence": "stop",
        }
        bedrock_reason = payload.get("stopReason", "end_turn")
        out.append({"choices": [{
            "delta": {},
            "finish_reason": reason_map.get(bedrock_reason, "stop"),
        }]})

    elif event_type == "metadata":
        usage = payload.get("usage", {})
        if usage:
            out.append({"usage": {
                "prompt_tokens": usage.get("inputTokens", 0),
                "completion_tokens": usage.get("outputTokens", 0),
                "total_tokens": usage.get("totalTokens", 0),
            }})

    return out


# ── Response non-stream: Converse → format {"text","tool_calls"} ──────────
def parse_converse_response(body: dict) -> dict:
    """
    Dùng bởi _call_simple() (non-streaming, vd compact history) — dịch
    response Converse API (non-stream) thành format {"text", "tool_calls"}
    mà code cũ đang trả về cho mọi provider khác.
    """
    msg = body.get("output", {}).get("message", {})
    text = ""
    tool_calls = []
    for block in msg.get("content", []):
        if "text" in block:
            text += block["text"]
        elif "toolUse" in block:
            tu = block["toolUse"]
            tool_calls.append({
                "id": tu.get("toolUseId", ""),
                "type": "function",
                "function": {
                    "name": tu.get("name", ""),
                    "arguments": json.dumps(tu.get("input", {})),
                },
            })
    return {"text": text, "tool_calls": tool_calls}


# ── Models list (ListFoundationModels) ─────────────────────────────────────
def parse_models(data: dict) -> list[str]:
    """
    parse_models cho entry 'aws_bedrock' trong PROVIDERS dict — nhận response
    JSON đã được fetch_models() gọi qua _provider_request("list_models", ...),
    trả về list model ID. Chỉ giữ model hỗ trợ TEXT + tool use (loại embedding,
    image-gen).
    """
    out = []
    for m in data.get("modelSummaries", []):
        model_id = m.get("modelId", "")
        if not model_id:
            continue
        modalities_in  = m.get("inputModalities", [])
        modalities_out = m.get("outputModalities", [])
        if "TEXT" not in modalities_in or "TEXT" not in modalities_out:
            continue
        out.append(model_id)
    return out


# ── /end AWS BEDROCK ADAPTER ────────────────────────────────────────────────
