# ##== MCP (Model Context Protocol) ==##
# Chỉ active khi _active_provider == "commandcode" (provider có "mcp_capable").
# MCP server config lưu trong config.json key "mcp_servers":
#   { "<name>": {"transport":"http","url":"...", "headers":{...}, "enabled":true} }
#
# Tools của MCP server được merge vào api_tools gửi lên model dưới dạng
# function-tool với tên mcp__<server>__<tool> (đúng convention Command Code docs).
# Khi model gọi 1 tool như vậy, _dispatch_tool route sang _mcp_call_tool().

_MCP_TOOL_CACHE: dict = {}     # {server_name: [tool_dict, ...]} — cache trong session
_MCP_STATUS:     dict = {}     # {server_name: "connected"|"error"|"unauthorized"}
_MCP_LAST_ERROR: dict = {}     # {server_name: "HTTP 403: error code: 1010..."}

def mcp_is_active() -> bool:
    """MCP chỉ dùng khi provider active hỗ trợ (commandcode)."""
    return bool(_prov().get("mcp_capable"))

# Default MCP servers — tự động thêm vào config lần đầu nếu user chưa cấu hình
# gì, để người mới không cần biết cú pháp /mcp add vẫn có sẵn web search.
_DEFAULT_MCP_SERVERS = {
    "exa": {"transport": "http", "url": "https://mcp.exa.ai/mcp",
            "headers": {}, "enabled": True},
}

def mcp_servers_load() -> dict:
    cfg = load_config()
    if "mcp_servers" not in cfg:
        cfg["mcp_servers"] = dict(_DEFAULT_MCP_SERVERS)
        save_config(cfg)
    return cfg["mcp_servers"]

def mcp_servers_save(servers: dict):
    cfg = load_config()
    cfg["mcp_servers"] = servers
    save_config(cfg)

def mcp_add_server(name: str, url: str, headers: dict | None = None, transport: str = "http"):
    servers = mcp_servers_load()
    servers[name] = {"transport": transport, "url": url,
                      "headers": headers or {}, "enabled": True}
    mcp_servers_save(servers)
    _MCP_TOOL_CACHE.pop(name, None)
    _MCP_STATUS.pop(name, None)

def mcp_remove_server(name: str):
    servers = mcp_servers_load()
    if name in servers:
        del servers[name]
        mcp_servers_save(servers)
    _MCP_TOOL_CACHE.pop(name, None)
    _MCP_STATUS.pop(name, None)

def _mcp_request(server: dict, method: str, params: dict | None = None, timeout: int = 15):
    """Gửi 1 JSON-RPC request tới MCP server (HTTP transport). Trả về dict result hoặc raise."""
    url = server["url"]
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
    }
    headers.update(server.get("headers") or {})
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    # Một số MCP server trả về SSE (event: message\ndata: {...}) thay vì JSON thuần
    if raw.lstrip().startswith("event:") or raw.lstrip().startswith("data:"):
        data_lines = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            raw = "\n".join(data_lines).strip()
    data = json.loads(raw)
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data.get("result", {})

def mcp_fetch_tools(name: str, server: dict, force: bool = False) -> list:
    """tools/list cho 1 server, cache lại trong session."""
    if not force and name in _MCP_TOOL_CACHE:
        return _MCP_TOOL_CACHE[name]
    try:
        result = _mcp_request(server, "tools/list")
        tools = result.get("tools", [])
        _MCP_TOOL_CACHE[name] = tools
        _MCP_STATUS[name] = "connected"
        _MCP_LAST_ERROR.pop(name, None)
        return tools
    except urllib.error.HTTPError as e:
        _MCP_STATUS[name] = "unauthorized" if e.code in (401, 403) else "error"
        try:
            body = e.read().decode(errors="replace")[:200]
        except Exception:
            body = ""
        _MCP_LAST_ERROR[name] = f"HTTP {e.code}" + (f": {body}" if body else "")
        _MCP_TOOL_CACHE[name] = []
        return []
    except Exception as e:
        _MCP_STATUS[name] = "error"
        _MCP_LAST_ERROR[name] = str(e)
        _MCP_TOOL_CACHE[name] = []
        return []

def mcp_refresh_all(verbose: bool = False) -> dict:
    """Kết nối tới tất cả MCP server đã cấu hình + enabled. Trả về _MCP_STATUS."""
    servers = mcp_servers_load()
    if not servers:
        return {}
    for name, server in servers.items():
        if not server.get("enabled", True):
            continue
        if verbose:
            print(f"  {DIM}[mcp] đang kết nối {name}...{R}", end="", flush=True)
        tools = mcp_fetch_tools(name, server, force=True)
        if verbose:
            status = _MCP_STATUS.get(name, "error")
            n = len(tools)
            if status == "connected":
                print(f"\r  {GREEN}✓{R} {DIM}[mcp]{R} {WHITE}{name}{R}  {DIM}{n} tool(s){R}            ")
            elif status == "unauthorized":
                print(f"\r  {YELLOW}⚠{R} {DIM}[mcp]{R} {WHITE}{name}{R}  {YELLOW}cần xác thực (auth){R}            ")
            else:
                print(f"\r  {RED}✗{R} {DIM}[mcp]{R} {WHITE}{name}{R}  {RED}lỗi kết nối{R}            ")
    return _MCP_STATUS

def mcp_tools_as_openai_format() -> list:
    """Convert tools đã cache của các MCP server thành function-tool spec
    (OpenAI format) với tên mcp__<server>__<tool>, để merge vào api_tools."""
    out = []
    servers = mcp_servers_load()
    for name, server in servers.items():
        if not server.get("enabled", True):
            continue
        tools = mcp_fetch_tools(name, server)
        for t in tools:
            tool_name = t.get("name", "")
            if not tool_name:
                continue
            out.append({
                "type": "function",
                "function": {
                    "name": f"mcp__{name}__{tool_name}",
                    "description": (t.get("description") or "")[:1024],
                    "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
                }
            })
    return out

def mcp_call_tool(full_name: str, args: dict) -> str:
    """Dispatch mcp__<server>__<tool> → tools/call trên server tương ứng."""
    # Tách theo server name đã biết (an toàn hơn regex khi server/tool có "_")
    servers = mcp_servers_load()
    server_name = None
    tool_name   = None
    for sname in servers:
        prefix = f"mcp__{sname}__"
        if full_name.startswith(prefix):
            server_name = sname
            tool_name   = full_name[len(prefix):]
            break
    if not server_name:
        return f"[mcp_error: không tìm thấy server cho tool '{full_name}']"
    server = servers[server_name]
    if not server.get("enabled", True):
        return f"[mcp_error: server '{server_name}' đang bị disable]"
    try:
        result = _mcp_request(server, "tools/call",
                               {"name": tool_name, "arguments": args}, timeout=60)
        content = result.get("content", [])
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        if result.get("isError"):
            return f"[mcp_error] {' '.join(parts)}"
        return "\n".join(parts) if parts else "(no content)"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            _MCP_STATUS[server_name] = "unauthorized"
            return f"[mcp_error: {server_name} cần xác thực — dùng /mcp để kiểm tra]"
        return f"[mcp_error: HTTP {e.code}]"
    except Exception as e:
        return f"[mcp_error: {e}]"

def mcp_status_summary() -> str:
    """Dòng tóm tắt trạng thái MCP để hiện trong header/banner."""
    servers = mcp_servers_load()
    enabled = {n: s for n, s in servers.items() if s.get("enabled", True)}
    if not enabled:
        return f"{DIM}MCP: chưa cấu hình server (cmd mcp add ...){R}"
    parts = []
    for name in enabled:
        status = _MCP_STATUS.get(name)
        if status == "connected":
            n = len(_MCP_TOOL_CACHE.get(name, []))
            parts.append(f"{GREEN}●{R} {name}({n})")
        elif status == "unauthorized":
            parts.append(f"{YELLOW}●{R} {name}(auth)")
        elif status == "error":
            parts.append(f"{RED}●{R} {name}(err)")
        else:
            parts.append(f"{GRAY}●{R} {name}(?)")
    return f"{DIM}MCP:{R} " + "  ".join(parts)

# ── /end MCP ──────────────────────────────────────────────────────────────────


FW_DATA_NAME      = ".fw_data"           # hidden folder trong cwd — KHÔNG xuất hiện ở bất kỳ tool nào
DATA_DIR          = Path.cwd() / FW_DATA_NAME   # mọi data lưu cạnh project, không rải ra ~/.fw
DB_PATH           = DATA_DIR / "sessions.db"
CONFIG_PATH       = DATA_DIR / "config.json"
HISTORY_PATH      = DATA_DIR / "history"
HISTORY_MAX       = 500     # số dòng tối đa lưu
CHARS_PER_TOKEN   = 4
KEEP_RECENT       = 8   # giữ nhiều context hơn khi compact

COMPACT_RATIO_SOFT = 0.80  # compact nhẹ khi > 80% (tăng từ 65% để giữ prefix cache lâu hơn)
COMPACT_RATIO_HARD = 0.85  # compact mạnh khi > 85%
COMPACT_THRESHOLD = 100_000 # fallback nếu model không match

