# ##== PROVIDER ==##
# Tất cả config liên quan đến AI provider tập trung tại đây.
# Để thêm provider mới: thêm 1 entry vào PROVIDERS dict bên dưới.

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
    "cohere": {
        "name":         "Cohere",
        # Cohere Compatibility API — endpoint OpenAI-compatible chính thức,
        # hỗ trợ đầy đủ chat/completions streaming + function calling.
        "base_url":     "https://api.cohere.com/compatibility/v1",
        "models_url":   "https://api.cohere.com/v1/models?endpoint=chat&page_size=1000",
        "key_check_url":"https://api.cohere.com/v1/models?endpoint=chat&page_size=1",
        "env_key":      "COHERE_API_KEY",
        "config_key":   "cohere_api_key",
        "fallback_models": [
            "command-r-plus-08-2024",
            "command-r-08-2024",
            "command-r7b-12-2024",
        ],
        "context_limits": {
            "command-a-plus":   256_000,
            "command-a":        256_000,
            "north-mini-code":  256_000,
            "command-r-plus":   128_000,
            "command-r7b":      128_000,
            "command-r":        128_000,
        },
        # /v1/models trả về {"models": [{"name": ..., "endpoints": [...]}]}
        # endpoint=chat đã filter ở query string nhưng vẫn lẫn nhiều model
        # không hợp dùng qua pipeline OpenAI-compat hiện tại:
        #   - aya-*, tiny-aya-*     : đa ngôn ngữ, không tối ưu code/tool-use
        #   - *-vision-*            : multimodal, code này chỉ gửi text
        #   - *-translate-*         : chuyên dịch thuật
        #   - *-reasoning-*         : trả "thinking" block riêng, format
        #                             khác chuẩn OpenAI → vỡ _stream_response
        #   - *-arabic-*            : fine-tune riêng tiếng Ả Rập
        # Chỉ giữ lại Command (A/A+/R-plus/R/R7B) và North Mini Code.
        "parse_models":     lambda data: [
            m["name"] for m in data.get("models", [])
            if m.get("name") and "chat" in (m.get("endpoints") or [])
            and not any(x in m["name"].lower() for x in (
                "aya", "vision", "translate", "reasoning", "arabic",
                "command-a-03",   # tool calling không thật, chỉ hallucinate
                "north-mini-code",# stuck loop hỏi mãi, không bao giờ action
            ))
        ],
        "rate_limit_delay": 0.0,
    },
    "cerebras": {
        "name":         "Cerebras",
        # Cerebras Inference — OpenAI-compatible API, hỗ trợ streaming +
        # function calling. Chạy trên wafer-scale chip → tốc độ rất cao.
        "base_url":     "https://api.cerebras.ai/v1",
        "models_url":   "https://api.cerebras.ai/v1/models",
        "key_check_url":"https://api.cerebras.ai/v1/models",
        "env_key":      "CEREBRAS_API_KEY",
        "config_key":   "cerebras_api_key",
        "fallback_models": [
            "zai-glm-4.7",
            "gpt-oss-120b",
        ],
        "context_limits": {
            "zai-glm-4.7":   131_072,
            "gpt-oss-120b":  128_000,
        },
        # /v1/models trả về OpenAI-compatible format: {"data": [{"id": ...}]}
        # Chỉ giữ 2 model test được — bỏ các model embed / audio / vision
        "parse_models":     lambda data: [
            m["id"] for m in data.get("data", [])
            if m.get("id") and m["id"] in ("zai-glm-4.7", "gpt-oss-120b")
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
    "mercury": {
        "name":         "Mercury 2 (Inception Labs)",
        "base_url":     "https://api.inceptionlabs.ai/v1",
        "models_url":   None,
        "key_check_url": None,
        "env_key":      "INCEPTION_API_KEY",
        "config_key":   "inception_api_key",
        "fallback_models": [
            "mercury-2",
        ],
        "context_limits": {
            "mercury-2": 128_000,
        },
        "parse_models":     lambda data: [],
        "rate_limit_delay": 0.0,
    },
    "mara": {
        "name":         "Mara Cloud",
        # OpenAI-compatible inference API — powered by SambaNova hardware.
        # Endpoint: https://api.cloud.mara.com/v1
        # Model ID dạng plain string (ví dụ: "DeepSeek-V3.1", "gpt-oss-120b")
        # Trả về token usage chuẩn OpenAI (prompt_tokens / completion_tokens).
        # Không có cached_tokens riêng → không cần thêm vào _CACHE_PROVIDERS.
        "base_url":     "https://api.cloud.mara.com/v1",
        "models_url":   "https://api.cloud.mara.com/v1/models",
        "key_check_url":"https://api.cloud.mara.com/v1/models",
        "env_key":      "MARA_API_KEY",
        "config_key":   "mara_api_key",
        "fallback_models": [
            "DeepSeek-V3.1",
            "gpt-oss-120b",
            "MiniMax-M2.5",
            "MiniMax-M2.7",
        ],
        "context_limits": {
            "DeepSeek-V3.1":  128_000,
            "DeepSeek-R1":    128_000,
            "gpt-oss-120b":   128_000,
            "gpt-oss-20b":    128_000,
            "MiniMax-M2.5":   128_000,
            "MiniMax-M2.7":   128_000,
            "Llama":          128_000,
            "Qwen":           128_000,
        },
        # /v1/models trả về OpenAI-compatible format: {"data": [{"id": ...}]}
        # Lọc bỏ embed / moderation / tts / vision / rerank
        "parse_models": lambda data: [
            m["id"] for m in data.get("data", [])
            if m.get("id") and not any(x in m["id"].lower() for x in (
                "embed", "moderation", "tts", "whisper", "dall-e", "rerank",
            ))
        ],
        "rate_limit_delay": 0.0,
    },
    "requesty": {
        "name":         "Requesty AI",
        # OpenAI-compatible gateway — route tới 550+ model từ nhiều provider.
        # Model ID dạng: provider/model-name  (vd: anthropic/claude-sonnet-4-6)
        "base_url":     "https://router.requesty.ai/v1",
        "models_url":   "https://router.requesty.ai/v1/models",
        "key_check_url":"https://router.requesty.ai/v1/models",
        "env_key":      "REQUESTY_API_KEY",
        "config_key":   "requesty_api_key",
        # Các free model (200 req/day) — xếp đầu danh sách
        # Model ID đầy đủ tra tại: https://requesty.ai/models
        "free_models": [
            "google/gemma-4-31b-it",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia/nemotron-nano-omni-30b-a3b-reasoning",
            "nvidia/nemotron-3-nano-30b-a3b",
            "nvidia/nemotron-3.5-content-safety",
            "poolside/laguna-m.1",
            "poolside/laguna-xs.2",
        ],
        # Vùng hỗ trợ của từng free model (None = Global)
        "free_model_regions": {
            "google/gemma-4-31b-it":                        None,       # Global
            "nvidia/nemotron-3-ultra-550b-a55b":            "US",
            "nvidia/nemotron-3-super-120b-a12b":            "US",
            "nvidia/nemotron-nano-omni-30b-a3b-reasoning":  "US",
            "nvidia/nemotron-3-nano-30b-a3b":               "US",
            "nvidia/nemotron-3.5-content-safety":           "US",
            "poolside/laguna-m.1":                          "US",
            "poolside/laguna-xs.2":                         "US",
        },
        # Vùng khả dụng khi người dùng chọn model có region_hint
        "regions": ["Global", "US", "EU"],
        "fallback_models": [
            "google/gemma-4-31b-it",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "nvidia/nemotron-3-super-120b-a12b",
            "anthropic/claude-sonnet-4-6",
            "openai/gpt-4o",
            "google/gemini-2.5-pro",
            "deepseek/deepseek-v3",
        ],
        "context_limits": {
            "claude-sonnet":    200_000,
            "claude-opus":      200_000,
            "claude-haiku":     200_000,
            "gpt-4o":           128_000,
            "gpt-4":            128_000,
            "gemini-2.5":     1_000_000,
            "gemini-1.5":     1_000_000,
            "deepseek-v3":      128_000,
            "deepseek-r1":      128_000,
            "nemotron":       1_000_000,
            "gemma-4":          262_000,
            "llama":            128_000,
            "qwen":             128_000,
            "laguna":            33_000,
        },
        # /v1/models trả về OpenAI-compatible {data: [{id, ...}]}
        # Lọc bỏ embed/rerank/moderation
        "parse_models": lambda data: [
            m["id"] for m in data.get("data", [])
            if m.get("id") and not any(x in m["id"].lower() for x in (
                "embed", "rerank", "moderation", "whisper", "tts", "dall-e",
            ))
        ],
        "rate_limit_delay": 0.0,
    },
    "aws_bedrock": {
        "name":         "AWS Bedrock",
        # Bedrock dùng Bedrock API Key (Bearer token, tạo trong Console →
        # Bedrock → API keys) — vẫn đi qua aws.build_request() vì URL
        # endpoint khác hẳn OpenAI-style (phụ thuộc region + model_id nằm
        # trong path). base_url/models_url ở đây chỉ là cờ hiệu cho
        # _provider_request() nhận biết, không phải URL thật.
        "base_url":     "aws_bedrock",
        "models_url":   "list_models",
        "key_check_url":"list_models",
        # Lưu dạng "{region}|{api_key}" vào đúng 1 field string này —
        # aws.parse_credentials() tự tách ra. Ví dụ: us-east-1|bedrock-api-key-xxxx
        "env_key":      "AWS_BEDROCK_API_KEY",
        "config_key":   "aws_bedrock_api_key",
        "fallback_models": [
            "anthropic.claude-sonnet-4-6-v1:0",
            "anthropic.claude-haiku-4-5-v1:0",
            "meta.llama3-3-70b-instruct-v1:0",
        ],
        "context_limits": {
            "claude-sonnet": 200_000,
            "claude-haiku":  200_000,
            "claude-opus":   200_000,
            "llama3":        128_000,
        },
        "parse_models":     lambda data: parse_models(data),
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
    if _active_provider == "aws_bedrock":
        # Bedrock: auth SigV4 + Converse API hoàn toàn khác OpenAI-style.
        # Toàn bộ phần đó nằm trong 01b_aws.py — ở đây chỉ chuyển tiếp.
        # path == "list_models" (cờ hiệu, không phải URL thật) → list model.
        # path == "/chat/completions" → chat turn, model lấy từ payload.
        bedrock_payload = dict(payload) if payload else {}
        if path == "list_models":
            bedrock_path = "list_models"
        else:
            bedrock_path = "converse"
        return build_request(bedrock_path, api_key, bedrock_payload,
                              extra_headers=extra_headers)

    # Anthropic Messages API format (custom provider với format_anthropic=True)
    if _prov().get("format_anthropic"):
        # path vào đây là:
        #   - URL đầy đủ (key_check_url, models_url): "https://...../models"
        #   - path tương đối từ call_api_stream: "/chat/completions"
        # build_anthropic_request đã tự handle startswith("http"):
        #   - URL đầy đủ → dùng trực tiếp
        #   - path tương đối → ghép base_url + path
        # Chỉ cần dịch "/chat/completions" → "/messages" cho chat.
        anth_path = "/messages" if path == "/chat/completions" else path
        return build_anthropic_request(
            anth_path, api_key,
            payload=payload,
            extra_headers=extra_headers,
            base_url=_prov().get("base_url", "https://api.anthropic.com/v1"),
            anthropic_version=_prov().get("anthropic_version", ANTHROPIC_DEFAULT_VERSION),
            auth_mode=_prov().get("anthropic_auth_mode", "x-api-key"),
        )

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

    # Requesty: gắn region header nếu đã chọn vùng
    # B1 FIX: code cũ tự build path qua Path(__file__).parent.parent — sai vì
    # sau khi tách module, __file__ trong namespace exec luôn là đường dẫn
    # fw.py (loader), KHÔNG phải đường dẫn của module này. Dùng load_config()
    # thật (CONFIG_PATH = cwd/.fw_data/config.json) — đúng nơi save_config()
    # ghi, và load_config() đã tự bắt Exception nên không cần try/except riêng.
    if _active_provider == "requesty" and payload is not None:
        _region = load_config().get("requesty_region", "")
        if _region and _region.lower() != "global":
            headers["x-requesty-region"] = _region.lower()

    return urllib.request.Request(url, data=data, headers=headers)

# ── Custom provider (lưu/load từ config.json) ────────────────────────────────
def _load_custom_providers() -> dict:
    """Load custom providers đã lưu từ config.json → {key: provider_dict}."""
    try:
        cfg = load_config()
        return cfg.get("custom_providers", {})
    except Exception:
        return {}

def _save_custom_providers(custom: dict):
    """Ghi custom providers vào config.json."""
    try:
        cfg = load_config()
        cfg["custom_providers"] = custom
        save_config(cfg)
    except Exception:
        pass

def _add_custom_provider():
    """
    Wizard thêm provider OpenAI-compatible mới.
    Hỏi: tên, base_url, api_key env var, models_url (auto/manual/none).
    Lưu vào config.json và inject vào PROVIDERS ngay.
    """
    print(f"\n  {CYAN}{BOLD}Thêm Provider OpenAI-Compatible / Anthropic{R}")
    print(f"  {DIM}Hỗ trợ: format OpenAI (/v1/chat/completions) và Anthropic Messages API.{R}\n")

    def _ask(prompt, default=""):
        hint = f" {DIM}[{default}]{R}" if default else ""
        try:
            val = input(f"  {YELLOW}❯{R} {prompt}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return default
        return val or default

    # ── 1. Tên hiển thị ──────────────────────────────────────────────────────
    name = ""
    while not name:
        name = _ask("Tên provider (vd: My API)")
        if not name:
            print(f"  {RED}Bắt buộc nhập tên.{R}")

    # ── 2. Base URL ───────────────────────────────────────────────────────────
    # Nhận diện thông minh: nếu user dán URL có endpoint path, tự strip về base
    # và gợi ý format phù hợp làm default cho bước kế tiếp.
    #
    # Ví dụ:
    #   https://api.openmodel.ai/v1/messages      → base: .../v1  | suggest: anthropic
    #   https://api.openmodel.ai/v1/chat/completions → base: .../v1 | suggest: openai
    #   https://api.openmodel.ai/v1               → base: .../v1  | suggest: không đổi
    _ANTHROPIC_SUFFIXES = ("/messages", "/v1/messages")
    _OPENAI_SUFFIXES    = ("/chat/completions", "/v1/chat/completions")
    _fmt_suggest = None   # None = chưa đủ thông tin để gợi ý

    base_url = ""
    while not base_url:
        base_url = _ask("Base URL (vd: https://api.example.com/v1)")
        if not base_url:
            print(f"  {RED}Bắt buộc nhập base URL.{R}")
    base_url = base_url.rstrip("/")

    # Detect và strip endpoint suffix nếu có
    _stripped = False
    for _sfx in _ANTHROPIC_SUFFIXES:
        if base_url.endswith(_sfx):
            base_url = base_url[:-len(_sfx)].rstrip("/")
            _fmt_suggest = "anthropic"
            _stripped = True
            break
    if not _stripped:
        for _sfx in _OPENAI_SUFFIXES:
            if base_url.endswith(_sfx):
                base_url = base_url[:-len(_sfx)].rstrip("/")
                _fmt_suggest = "openai"
                _stripped = True
                break

    if _stripped:
        _suggest_label = "Anthropic" if _fmt_suggest == "anthropic" else "OpenAI"
        print(f"  {GREEN}✓ Base URL:{R} {WHITE}{base_url}{R}"
              f"  {DIM}(đã strip endpoint path, gợi ý format: {_suggest_label}){R}")

    # ── 3. Format API ─────────────────────────────────────────────────────────
    # Default gợi ý từ URL nếu detect được, không thì mặc định openai (1)
    _fmt_default = "2" if _fmt_suggest == "anthropic" else "1"
    print(f"\n  {DIM}Format API:{R}")
    print(f"  {YELLOW}1{R}  OpenAI-compatible  {DIM}(/v1/chat/completions){R}")
    print(f"  {YELLOW}2{R}  Anthropic Messages API  {DIM}(/v1/messages, SSE Anthropic-style){R}\n")
    fmt_raw = _ask("Chọn format", _fmt_default).strip()
    use_anthropic_format = (fmt_raw == "2")
    if use_anthropic_format:
        print(f"  {GREEN}✓ Dùng Anthropic Messages API format.{R}\n")
    else:
        print(f"  {GREEN}✓ Dùng OpenAI-compatible format.{R}\n")

    # ── 4. Link lấy API key ───────────────────────────────────────────────────
    print(f"\n  {DIM}Link trang lấy API key (hiện khi hỏi key lần đầu).{R}")
    print(f"  {DIM}Bỏ trống / none nếu không có.{R}\n")
    key_url_raw = _ask("Link API key", "none").strip()
    key_url = "" if key_url_raw.lower() in ("none", "no", "") else key_url_raw

    # ── 4. API Key env var ────────────────────────────────────────────────────
    # Tự gợi ý từ tên (MY_API → MY_API_KEY)
    suggested_env = name.upper().replace(" ", "_").replace("-", "_") + "_API_KEY"
    env_key = _ask(f"Tên biến môi trường API key", suggested_env)

    # config_key: lowercase slug
    import re as _re
    config_key = _re.sub(r"[^a-z0-9_]", "_",
                         name.lower().replace(" ", "_")) + "_api_key"

    # ── 5. Models URL ─────────────────────────────────────────────────────────
    print(f"\n  {DIM}Models URL — nhập một trong ba:{R}")
    print(f"  {DIM}  • URL endpoint GET /models  (vd: https://api.example.com/v1/models){R}")
    print(f"  {DIM}  • {CYAN}auto{R}{DIM}  — tự ghép base_url + /models{R}")
    print(f"  {DIM}  • {CYAN}none{R}{DIM}  — không có endpoint, tự nhập model bằng tay{R}\n")
    models_url_raw = _ask("Models URL", "auto").lower()
    if models_url_raw in ("", "auto"):
        models_url = base_url + "/models"
    elif models_url_raw in ("none", "không", "ko", "no"):
        models_url = None
    else:
        models_url = models_url_raw

    # ── 6. Fallback models ────────────────────────────────────────────────────
    print(f"\n  {DIM}Fallback models — dùng khi không fetch được danh sách.{R}")
    print(f"  {DIM}Nhập {CYAN}auto{R}{DIM} để tự fetch khi chọn, hoặc nhập tên model cách nhau dấu phẩy.{R}\n")
    fb_raw = _ask("Fallback models", "auto")
    if fb_raw.strip().lower() in ("", "auto"):
        fallback_models = []
    else:
        fallback_models = [m.strip() for m in fb_raw.split(",") if m.strip()]

    # ── 7. Tạo key (slug) cho PROVIDERS dict ─────────────────────────────────
    base_key = _re.sub(r"[^a-z0-9]", "_", name.lower())[:20].strip("_")
    # Tránh trùng với key đã có
    prov_key = base_key
    suffix = 2
    while prov_key in PROVIDERS:
        prov_key = f"{base_key}_{suffix}"; suffix += 1

    # ── 8. Xây provider dict ──────────────────────────────────────────────────
    # parse_models mặc định theo format
    if use_anthropic_format:
        _default_parse = lambda data: parse_anthropic_models(data)  # noqa: E731
    else:
        _default_parse = lambda data: [          # chuẩn OpenAI {data:[{id}]}  # noqa: E731
            m["id"] for m in data.get("data", [])
            if m.get("id") and not any(x in m["id"].lower() for x in (
                "embed", "moderation", "tts", "whisper", "dall-e", "rerank",
            ))
        ]

    new_prov = {
        "name":             name,
        "base_url":         base_url,
        "models_url":       models_url,
        "key_check_url":    models_url,
        "env_key":          env_key,
        "config_key":       config_key,
        "fallback_models":  fallback_models,
        "context_limits":   {},
        "parse_models":     _default_parse,
        "rate_limit_delay": 0.0,
        "key_url":          key_url,  # link lấy key — hiện trong get_api_key wizard
        "_custom":          True,     # đánh dấu để phân biệt
        "format_anthropic": use_anthropic_format,  # True → dùng Anthropic Messages API
    }

    # ── 9. Lưu và inject ─────────────────────────────────────────────────────
    PROVIDERS[prov_key] = new_prov
    custom = _load_custom_providers()
    # Serialise: bỏ lambda (không JSON-able), sẽ rebuild khi load lại
    serial = {k: v for k, v in new_prov.items() if k != "parse_models"}
    custom[prov_key] = serial
    _save_custom_providers(custom)

    print(f"\n  {GREEN}✓ Đã thêm provider:{R} {WHITE}{name}{R}"
          f"  {DIM}(key: {prov_key}){R}\n")
    return prov_key

def _rebuild_custom_parse(prov_dict: dict) -> dict:
    """Thêm lại parse_models lambda cho custom provider load từ JSON."""
    if "_custom" in prov_dict and "parse_models" not in prov_dict:
        if prov_dict.get("format_anthropic"):
            prov_dict["parse_models"] = lambda data: parse_anthropic_models(data)
        else:
            prov_dict["parse_models"] = lambda data: [
                m["id"] for m in data.get("data", [])
                if m.get("id") and not any(x in m["id"].lower() for x in (
                    "embed", "moderation", "tts", "whisper", "dall-e", "rerank",
                ))
            ]
    return prov_dict

# ── Provider selector (gọi 1 lần khi startup) ────────────────────────────────
def choose_provider() -> str:
    """Hiện menu chọn provider. Trả về key (vd 'fireworks', 'mistral')."""
    global _active_provider

    # Nạp custom providers đã lưu vào PROVIDERS trước khi hiện menu
    for k, v in _load_custom_providers().items():
        if k not in PROVIDERS:
            PROVIDERS[k] = _rebuild_custom_parse(dict(v))

    w = shutil.get_terminal_size((80, 20)).columns
    box_w = min(w - 2, 60)

    def _print_menu():
        keys = list(PROVIDERS.keys())
        print()
        print(f"  {CYAN}{BOLD}Open CLI Codex{R}  {DIM}— select provider{R}")
        print(f"  {DIM}{'─' * box_w}{R}")
        for i, k in enumerate(keys, 1):
            p = PROVIDERS[k]
            tag = f" {DIM}[custom]{R}" if p.get("_custom") else ""
            env_hint = f"{GRAY}  {p['env_key']}{R}"
            print(f"  {YELLOW}{BOLD}{i}{R}  {WHITE}{p['name']}{R}{tag}{env_hint}")
        print(f"  {DIM}{'─' * box_w}{R}")
        print(f"  {YELLOW}T{R}{DIM}  Thêm provider OpenAI-compatible mới{R}")
        print()
        return keys

    keys = _print_menu()

    while True:
        try:
            n = input(f"  {CYAN}❯ {DIM}[1]{R} ").strip()
            if not n:
                n = "1"

            # ── T: thêm provider mới ─────────────────────────────────────────
            if n.lower() == "t":
                new_key = _add_custom_provider()
                # Vẽ lại menu (có provider mới)
                keys = _print_menu()
                continue

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

