# ##== PROVIDER ==##
# Tất cả config liên quan đến AI provider tập trung tại đây.
# Để thêm provider mới: thêm 1 entry vào PROVIDERS dict bên dưới.

EXA_MCP_URL = "https://mcp.exa.ai/mcp"

# ── Provider registry ─────────────────────────────────────────────────────────
# Mỗi provider là 1 dict với các keys bắt buộc:
#   name          : tên hiển thị
#   base_url      : endpoint chat completions (prefix cho path tương đối)
#   models_url    : GET endpoint để list models
#   key_check_url : GET endpoint để validate API key (thường = models_url)
#   env_key       : tên biến môi trường chứa API key
#   config_key    : key trong config.json để lưu API key
#   fallback_models : list model dùng khi fetch_models thất bại
#   context_limits  : {model_short_name: int} — conservative token limit
#   parse_models  : callable(data: dict) → list[str] — parse response từ models_url
#   rate_limit_delay: float — delay (giây) giữa các API call (0 = không delay)

PROVIDERS = {
    "fireworks": {
        "name":         "Fireworks AI",
        "base_url":     "https://api.fireworks.ai/inference/v1",
        "models_url":   "https://api.fireworks.ai/v1/accounts/fireworks/models"
                        "?page_size=100&filter=supports_serverless%3Dtrue",
        "key_check_url":"https://api.fireworks.ai/v1/accounts/fireworks/models?page_size=1",
        "env_key":      "FIREWORKS_API_KEY",
        "config_key":   "api_key",
        "fallback_models": [
            "accounts/fireworks/models/deepseek-v3p1",
            "accounts/fireworks/models/deepseek-r1",
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/llama-v3p1-405b-instruct",
            "accounts/fireworks/models/qwen3-235b-a22b",
            "accounts/fireworks/models/mixtral-8x22b-instruct",
            "accounts/fireworks/models/gemma2-9b-it",
        ],
        "context_limits": {
            "deepseek-v3":      128_000,
            "deepseek-v4":      128_000,
            "deepseek-r1":      128_000,
            "llama-v3p3-70b":   128_000,
            "llama-v3p1-405b":  128_000,
            "qwen3-235b":       128_000,
            "qwen3-30b":        128_000,
            "qwen3-coder":      128_000,
            "mixtral-8x22b":     32_000,
            "gemma2-9b":         16_000,
            "gemma-4":          128_000,
        },
        "parse_models":     lambda data: [
            m["name"] for m in data.get("models", [])
            if m.get("name") and m.get("serverlessDeployment", True)
        ],
        "rate_limit_delay": 0.0,
    },
    "mistral": {
        "name":         "Mistral AI",
        "base_url":     "https://api.mistral.ai/v1",
        "models_url":   "https://api.mistral.ai/v1/models",
        "key_check_url":"https://api.mistral.ai/v1/models",
        "env_key":      "MISTRAL_API_KEY",
        "config_key":   "mistral_api_key",
        "fallback_models": [
            "devstral-2512",
        ],
        "context_limits": {
            "devstral":         65_000,
            "mistral-large":    65_000,
            "mistral-medium":   32_000,
            "mistral-small":    32_000,
            "codestral":        65_000,
        },
        "parse_models":     lambda data: [
            m["id"] for m in data.get("data", [])
            if m.get("id") and not any(x in m["id"].lower() for x in (
                "voxtral", "embed", "moderation", "ocr", "tts", "transcribe"
            ))
        ],
        # Mistral free tier: ~0.67 req/s → delay 1.5s để an toàn
        "rate_limit_delay": 1.5,
    },
    "nvidia": {
        "name":         "NVIDIA NIM",
        "base_url":     "https://integrate.api.nvidia.com/v1",
        # Cloud NIM không có GET /v1/models → dùng fallback_models
        # User thêm model thủ công qua option T trong choose_model
        "models_url":   None,
        "key_check_url": None,
        "env_key":      "NVIDIA_API_KEY",
        "config_key":   "nvidia_api_key",
        "fallback_models": [
            "minimaxai/minimax-m2.7",
        ],
        "context_limits": {
            "minimax":  128_000,
            "kimi":     128_000,
            "deepseek": 128_000,
            "llama":    128_000,
            "qwen":     128_000,
            "gemma":    128_000,
            "nemotron":  65_000,
        },
        "parse_models":     lambda data: [],
        "rate_limit_delay": 0.0,
    },
    "commandcode": {
        "name":         "Command Code",
        # Dùng endpoint OpenAI-compatible — toàn bộ pipeline streaming/tool-call
        # hiện tại (chat/completions) tái sử dụng được nguyên vẹn.
        "base_url":     "https://api.commandcode.ai/provider/v1",
        "models_url":   "https://api.commandcode.ai/provider/v1/models",
        "key_check_url":"https://api.commandcode.ai/provider/v1/models",
        "env_key":      "COMMANDCODE_API_KEY",
        "config_key":   "commandcode_api_key",
        "fallback_models": [
            "claude-sonnet-4-6",
            "deepseek/deepseek-v4-flash",
        ],
        "context_limits": {
            "claude-sonnet": 200_000,
            "claude-opus":   200_000,
            "claude-haiku":  200_000,
            "deepseek":      128_000,
        },
        "parse_models":     lambda data: [
            m["id"] for m in data.get("data", [])
            if m.get("id")
        ],
        "rate_limit_delay": 0.0,
        # Provider này hỗ trợ MCP server — ưu tiên dùng MCP tools thay vì
        # webfetch/websearch nội bộ khi đã kết nối server.
        "mcp_capable":  True,
    },
    "mimo": {
        "name":         "Xiaomi (MiMo)",
        "base_url":     "https://api.xiaomimimo.com/v1",
        # MiMo không có GET /v1/models công khai → dùng fallback_models
        "models_url":   None,
        "key_check_url": None,
        "env_key":      "MIMO_API_KEY",
        "config_key":   "mimo_api_key",
        "fallback_models": [
            "mimo-v2.5-pro",
            "mimo-v2.5",
            "mimo-v2-pro",
            "mimo-v2-omni",
            "mimo-v2-flash",
        ],
        "context_limits": {
            "mimo-v2.5-pro":  128_000,
            "mimo-v2.5":      128_000,
            "mimo-v2-pro":    128_000,
            "mimo-v2-omni":   128_000,
            "mimo-v2-flash":  128_000,
        },
        "parse_models":     lambda data: [],
        "rate_limit_delay": 0.0,
    },
    "qwen": {
        "name":         "Qwen API (Singapore)",
        # DashScope Singapore workspace-specific endpoint (OpenAI-compatible)
        # Thay {WorkspaceId} bằng Workspace ID thực của bạn từ Model Studio console.
        # Nếu chưa set QWEN_WORKSPACE_ID, fallback về endpoint global dashscope-intl.
        "base_url":     "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        # DashScope có GET /v1/models trả về danh sách model
        "models_url":   "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
        "key_check_url":"https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
        "env_key":      "DASHSCOPE_API_KEY",
        "config_key":   "qwen_api_key",
        # Fallback models — các model Qwen phổ biến nhất trên DashScope
        "fallback_models": [
            # ── Qwen3 flagship ──────────────────────────────────────────────
            "qwen3-235b-a22b",          # MoE 235B, flagship
            "qwen3-32b",                # Dense 32B
            "qwen3-30b-a3b",            # MoE 30B
            "qwen3-14b",
            "qwen3-8b",
            # ── Qwen commercial (Max / Plus / Flash / Turbo) ────────────────
            "qwen-max",                 # alias → latest qwen-max snapshot
            "qwen-plus",                # alias → latest qwen-plus snapshot
            "qwen-turbo",
            "qwen-long",
            # ── Qwen Coder ──────────────────────────────────────────────────
            "qwen2.5-coder-32b-instruct",
            "qwen-coder-plus",
            # ── Qwen Math ───────────────────────────────────────────────────
            "qwen2.5-math-72b-instruct",
            # ── DeepSeek trên DashScope ─────────────────────────────────────
            "deepseek-v3",
            "deepseek-r1",
            # ── Kimi / GLM / MiniMax (re-sold qua DashScope) ────────────────
            "kimi-k2",
            "glm-4",
            "minimax-text-01",
        ],
        "context_limits": {
            # Qwen3 series
            "qwen3-235b":       131_072,
            "qwen3-32b":        131_072,
            "qwen3-30b":        131_072,
            "qwen3-14b":        131_072,
            "qwen3-8b":         131_072,
            # Qwen commercial
            "qwen-max":         131_072,
            "qwen-plus":        131_072,
            "qwen-turbo":       131_072,
            "qwen-long":      1_000_000,
            # Coder
            "qwen2.5-coder":    131_072,
            "qwen-coder":       131_072,
            # Math
            "qwen2.5-math":      32_768,
            # DeepSeek
            "deepseek-v3":      131_072,
            "deepseek-r1":      131_072,
            # Others
            "kimi":             131_072,
            "glm-4":            131_072,
            "minimax":          131_072,
        },
        # DashScope /v1/models trả về OpenAI-compatible format: {"data": [...]}
        # Lọc bỏ embedding / rerank / audio / image-gen để chỉ giữ LLM text
        "parse_models": lambda data: [
            m["id"] for m in data.get("data", [])
            if m.get("id") and not any(x in m["id"].lower() for x in (
                "embed", "rerank", "text-to-image", "wanx", "cosyvoice",
                "sambert", "paraformer", "qwen-vl", "qwen-audio", "omni",
                "ocr", "tts", "asr",
                # image gen / edit / vision
                "image", "wan", "-vl-",
                # audio / speech / translation
                "livetranslate", "s2s", "realtime", "tingwu",
                # machine translation API
                "-mt-",
            ))
        ],
        "rate_limit_delay": 0.0,
    },
}

# ── Active provider (set khi startup qua choose_provider()) ───────────────────
_active_provider: str = "fireworks"   # key vào PROVIDERS

def _prov() -> dict:
    """Trả về config dict của provider đang active."""
    return PROVIDERS[_active_provider]

# ── Compat aliases — code cũ dùng BASE_URL / MODEL_CONTEXT_LIMITS vẫn chạy ──
def _base_url() -> str:
    """Trả về base_url — với Qwen thì ưu tiên workspace-specific Singapore URL."""
    prov = _prov()
    if _active_provider == "qwen":
        ws_id = os.environ.get("QWEN_WORKSPACE_ID", "").strip()
        if ws_id:
            return f"https://{ws_id}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    return prov["base_url"]

def _qwen_models_url() -> str:
    """Trả về models_url cho Qwen — dùng workspace URL nếu có QWEN_WORKSPACE_ID."""
    ws_id = os.environ.get("QWEN_WORKSPACE_ID", "").strip()
    if ws_id:
        return f"https://{ws_id}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/models"
    return PROVIDERS["qwen"]["models_url"]

MODEL_CONTEXT_LIMITS: dict = {}   # populated dynamically by _prov()["context_limits"]

def _context_limits() -> dict:
    return _prov()["context_limits"]

# ── Rate limiter ──────────────────────────────────────────────────────────────
_last_api_call_time: float = 0.0

def _rate_limit_wait():
    """Sleep nếu cần để tôn trọng rate limit của provider active."""
    global _last_api_call_time
    delay = _prov().get("rate_limit_delay", 0.0)
    if delay <= 0:
        return
    elapsed = time.time() - _last_api_call_time
    if elapsed < delay:
        time.sleep(delay - elapsed)

def _rate_limit_mark():
    """Đánh dấu thời điểm vừa gọi API xong."""
    global _last_api_call_time
    _last_api_call_time = time.time()

# ── Request helper ────────────────────────────────────────────────────────────
def _provider_request(path: str, api_key: str, payload: dict | None = None,
                      timeout: int = 60, extra_headers: dict | None = None):
    """
    Gửi request tới provider active. path là URL đầy đủ hoặc path tương đối.
    payload=None → GET, payload=dict → POST JSON.
    Trả về urllib.request.Request — caller tự urlopen.
    """
    base = _base_url()
    url  = path if path.startswith("http") else f"{base}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if extra_headers:
        headers.update(extra_headers)
    return urllib.request.Request(url, data=data, headers=headers)

# ── Provider selector (gọi 1 lần khi startup) ────────────────────────────────
def choose_provider() -> str:
    """Hiện menu chọn provider. Trả về key (vd 'fireworks', 'mistral')."""
    global _active_provider
    keys = list(PROVIDERS.keys())
    w = shutil.get_terminal_size((80, 20)).columns
    box_w = min(w - 2, 56)

    print()
    print(f"  {CYAN}{BOLD}Open CLI Codex{R}  {DIM}— select provider{R}")
    print(f"  {DIM}{'─' * box_w}{R}")
    for i, k in enumerate(keys, 1):
        p = PROVIDERS[k]
        env_hint = f"{GRAY}  {p['env_key']}{R}"
        print(f"  {YELLOW}{BOLD}{i}{R}  {WHITE}{p['name']}{R}{env_hint}")
    print(f"  {DIM}{'─' * box_w}{R}")
    print()

    while True:
        try:
            n = input(f"  {CYAN}❯ {DIM}[1]{R} ").strip()
            if not n:
                n = "1"
            idx = int(n) - 1
            if 0 <= idx < len(keys):
                _active_provider = keys[idx]
                print(f"  {GREEN}✓{R} {DIM}Provider:{R} {WHITE}{PROVIDERS[_active_provider]['name']}{R}\n")
                if mcp_is_active():
                    servers = mcp_servers_load()
                    if servers:
                        print(f"  {DIM}Đang kết nối MCP server...{R}")
                        mcp_refresh_all(verbose=True)
                        print()
                    else:
                        print(f"  {DIM}MCP: chưa cấu hình server. Dùng /mcp add <name> <url> để thêm.{R}\n")
                return _active_provider
        except (ValueError, KeyboardInterrupt):
            print(f"\n  {DIM}Bye.{R}"); sys.exit(0)

# ── /end PROVIDER ─────────────────────────────────────────────────────────────

