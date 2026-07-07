```
   ____                      ____ _     ___    ____          _
  / __ \____  ___  ____     / ___| |   |_ _|  / ___|___   __| | _____  __
 / / / / __ \/ _ \/ __ \   | |   | |    | |  | |   / _ \ / _` |/ _ \ \/ /
/ /_/ / /_/ /  __/ / / /   | |___| |___ | |  | |__| (_) | (_| |  __/>  <
\____/ .___/\___/_/ /_/     \____|_____|___|  \____\___/ \__,_|\___/_/\_\
    /_/
```

<div align="center">

### A lightweight, stdlib‑only Python CLI coding agent

**12 AI providers · agentic tool loop · SQLite sessions · MCP support · zero heavyweight deps**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](#requirements)
[![Stdlib Only](https://img.shields.io/badge/dependencies-stdlib--only-brightgreen)](#requirements)
[![License: Proprietary](https://img.shields.io/badge/license-proprietary-red)](#license)
[![Providers](https://img.shields.io/badge/providers-12-orange)](#supported-providers)
[![Tools](https://img.shields.io/badge/agent%20tools-20-9cf)](#agent-tools)
[![Made with ❤️ in Vietnam](https://img.shields.io/badge/made%20with-%E2%9D%A4%EF%B8%8F%20in%20Vietnam-da251d)](#contact)

[English](#-english) · [Tiếng Việt](#-tiếng-việt)

</div>

---

<div align="center">

## 📖 Documentation

**Full guides live on the [project Wiki](https://github.com/phiiggfdg/Open-cli-codex/wiki)** — click any card below.

</div>

<table>
<tr>
<td width="33%" valign="top">

### 🚀 Getting Started

- 🏠 **[Wiki Home](https://github.com/phiiggfdg/Open-cli-codex/wiki/Home)**
  Overview, quick start, navigation
- 📦 **[Installation](https://github.com/phiiggfdg/Open-cli-codex/wiki/Installation)**
  pip install, run directly, Termux/Android
- 🔌 **[Providers](https://github.com/phiiggfdg/Open-cli-codex/wiki/Providers)**
  12 built-in providers + custom provider wizard

</td>
<td width="33%" valign="top">

### 🧠 Core Concepts

- 🏗️ **[Architecture](https://github.com/phiiggfdg/Open-cli-codex/wiki/Architecture)**
  Module map, shared `exec()` namespace, load order
- 🛠️ **[Agent Tools](https://github.com/phiiggfdg/Open-cli-codex/wiki/Agent-Tools)**
  All 21 built-in tools, grouped by category
- 🔒 **[Permissions & Sandbox](https://github.com/phiiggfdg/Open-cli-codex/wiki/Permissions-&-Sandbox)**
  Agent modes, per-tool permissions, sandboxing

</td>
<td width="33%" valign="top">

### ⚙️ Usage & Config

- ⌨️ **[Slash Commands](https://github.com/phiiggfdg/Open-cli-codex/wiki/Slash-Commands)**
  Every `/` command in the REPL
- 🧩 **[Custom Commands](https://github.com/phiiggfdg/Open-cli-codex/wiki/Custom-Commands)**
  Build your own slash commands
- 🔗 **[MCP Integration](https://github.com/phiiggfdg/Open-cli-codex/wiki/MCP-Integration)**
  Model Context Protocol support
- 🗂️ **[Configuration](https://github.com/phiiggfdg/Open-cli-codex/wiki/Configuration)**
  config.json, AGENTS.md, checkpoints, cache
- ❓ **[FAQ & Troubleshooting](https://github.com/phiiggfdg/Open-cli-codex/wiki/FAQ-&-Troubleshooting)**
  Common issues and fixes

</td>
</tr>
</table>

<div align="center">

[![Wiki](https://img.shields.io/badge/docs-wiki-blueviolet?logo=githubpages&logoColor=white)](https://github.com/phiiggfdg/Open-cli-codex/wiki)
[![Pages](https://img.shields.io/badge/pages-11-informational)](https://github.com/phiiggfdg/Open-cli-codex/wiki)

</div>

---

## Table of Contents

- [Ownership](#ownership)
- [Built With AI Assistance](#built-with-ai-assistance)
- [Overview](#overview)
- [Features](#features)
- [Supported Providers](#supported-providers)
- [Agent Tools](#agent-tools)
- [Local Web UI (`/web`)](#local-web-ui-web)
- [Codeweb Mode (`/codeweb`)](#codeweb-mode-codeweb)
- [Skill System](#skill-system)
- [API Key Pool & Rotation](#api-key-pool--rotation)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Disclaimer](#disclaimer)
- [Security & Terms of Use](#security--terms-of-use)
- [Data, Prompts & Intellectual Property](#data-prompts--intellectual-property)
- [License](#license)
- [Contact](#contact)

---

## 🇬🇧 English

### Ownership

> **This project — including all source code, system prompts, prompt engineering patterns, configurations, and design decisions — is the sole intellectual property of Trần Tuấn Phi.**
>
> All rights reserved. Unauthorized commercial use, redistribution, or publication is strictly prohibited.

---

### Built With AI Assistance

This project was designed, architected, and built by **Trần Tuấn Phi**. AI tools were used as coding assistants during development:

| AI Assistant | Role |
|---|---|
| **Claude** (Anthropic) | Primary coding assistant — architecture, logic, system prompt engineering |
| **ChatGPT** (OpenAI) | Second-opinion analysis and cross-verification |
| **Gemini** (Google) | Supplementary reference and review |

> All prompts, architectural decisions, tool designs, and creative direction originated from and remain the property of **Trần Tuấn Phi**. AI assistants were used as tools only — they do not hold any ownership or rights over this project.

---

### Overview

`fw.py` is a personal Python CLI coding agent built from scratch. It connects to multiple AI providers — OpenAI-compatible, Anthropic Messages API, and AWS Bedrock Converse — through a unified internal message format, and supports a full agentic loop with tool use, SQLite-based session persistence, and a modern terminal UI.

This project was developed as a personal tool and is shared publicly for reference and learning purposes only.

---

### Features

<details open>
<summary><strong>Core capabilities</strong></summary>

- **Multi-format provider engine** — OpenAI-compatible, Anthropic Messages API, and AWS Bedrock Converse, all normalized to one internal message shape
- **Agentic loop** with parallel tool calls, prompt-cache–aware history pruning, and auto-continue on truncated output
- **Multi-key pool with automatic rotation** — add several API keys per provider; on HTTP 429 the pool cools down the limited key and switches to a free one instead of blindly sleeping
- **SQLite session management** with automatic context compaction at ~80k tokens
- **MCP (Model Context Protocol)** client integration
- **Skill system** — on-demand `SKILL.md` loading via the `skill` tool for domain-specific guidance (opencode-compatible `.opencode/skills` layout too)
- **Local Web UI** (`/web`) — zero-dependency WebSocket bridge that mirrors the running CLI session in a browser tab, no separate process spawned
- **Sandboxed execution** — each session runs in its own isolated working directory
- **Undo/redo dispatch system** for file edits
- **Extended thinking / reasoning** support (Claude extended thinking, DeepSeek-style reasoning) with correct round-trip replay
- **Modern terminal UI** — gradient banners, braille spinners, gradient context bars
- **Stdlib-only core** — no heavyweight dependencies required to run

</details>

<details>
<summary><strong>Why a custom multi-format engine?</strong></summary>

Most CLI agents lock you into one API shape. `fw.py` internally speaks only OpenAI chat-completions format — two adapter modules translate to/from Anthropic Messages API and AWS Bedrock Converse (including binary event-stream parsing for Bedrock), so every tool, every prompt, and the entire agent loop is written once and works identically across all 12 providers.

</details>

---

### Supported Providers

12 providers are registered out of the box. You can also add **any** OpenAI-compatible or Anthropic-format endpoint through the in-app setup wizard.

| # | Provider | Env Variable |
|---|---|---|
| 1 | Fireworks AI | `FIREWORKS_API_KEY` |
| 2 | Cohere | `COHERE_API_KEY` |
| 3 | Cerebras | `CEREBRAS_API_KEY` |
| 4 | Mistral AI | `MISTRAL_API_KEY` |
| 5 | NVIDIA NIM | `NVIDIA_API_KEY` |
| 6 | Command Code | `COMMANDCODE_API_KEY` |
| 7 | Xiaomi (MiMo) | `MIMO_API_KEY` |
| 8 | Qwen API (Singapore / DashScope) | `DASHSCOPE_API_KEY` |
| 9 | Mercury 2 (Inception Labs) | `INCEPTION_API_KEY` |
| 10 | Mara Cloud | `MARA_API_KEY` |
| 11 | Requesty AI | `REQUESTY_API_KEY` |
| 12 | AWS Bedrock (Converse API) | `AWS_BEDROCK_API_KEY` |

> Plus: **custom provider wizard** — add any OpenAI-compatible or Anthropic-format (`format_anthropic=True`) endpoint at runtime, no code changes needed.

---

### Agent Tools

<details open>
<summary><strong>21 built-in tools</strong> (click to expand schema names)</summary>

| Category | Tools |
|---|---|
| **Shell** | `bash` |
| **File I/O** | `read`, `write`, `edit`, `multiedit`, `extract`, `apply_patch` |
| **Search** | `glob`, `grep`, `view_symbol`, `file_index` |
| **Web** | `webfetch`, `websearch` |
| **Planning** | `todowrite`, `todoread`, `question`, `verify` |
| **Code intelligence** | `lsp` |
| **Orchestration** | `task` (subagent dispatch), `skill` |

</details>

---

### Local Web UI (`/web`)

Type `/web` in the running CLI to open a local browser bridge — **no separate process is spawned**. The browser tab connects via WebSocket to the *same* `SessionState` your CLI session already has (same messages, same model, same context).

- **Zero extra dependencies** — the WebSocket server (RFC 6455 handshake, framing) is hand-rolled on top of `http.server`/`socketserver`, no Flask/FastAPI/websockets package needed.
- **CLI keyboard locks while armed** — input is read from the browser instead; press `Esc` (or `Ctrl-C`) on the real terminal to instantly hand keyboard control back. The web server keeps running in the background either way.
- **Live event mirroring** — every `Event` your session emits (text deltas, tool calls, tool results, thinking, todo updates) is pushed to the browser as JSON in real time, not just a terminal byte-stream replay.
- **Slash commands are CLI-only by design** — typing `/something` or `exit`/`quit`/`q` from the web client is rejected with a warning; the Web UI is for chatting and watching the agent work, not for driving REPL commands. Switch back to the real terminal (`Esc`) to run commands.
- **Single active session** — the web bridge always mirrors whichever `SessionState` is currently registered as the CLI's session (e.g. switching sessions via `/sessions` re-points the bridge automatically).
- **Image support** — attach images directly from the browser; only `/web` can send them (the real keyboard has no such path). Each incoming image is validated server-side before it reaches the model: unsupported MIME types are dropped with a warning, oversized base64 payloads (unresized full-res photos) are rejected with the limit shown, and up to 6 images per turn are accepted. The frontend also learns per-model whether the currently selected model is known to support vision, so it doesn't blindly unlock the image button every time.

```
/web
# → Web UI running: http://127.0.0.1:8765/
# → CLI input locked — use the browser.
# → Press Esc to return to the CLI (web server keeps running in background).
```

> Implemented in `12_web.py`. Architecture note: an earlier PTY-spawn design (browser as a dumb terminal emulator) was replaced with this direct `EventBus` bridge so the browser can render structured tool cards/JSON instead of raw ANSI bytes.

---

### Codeweb Mode (`/codeweb`)

A focused sub-mode of `/web`, purpose-built for frontend work: a two-column layout where the left side keeps the normal chat/tool log and the right side is a **live preview pane** that updates automatically every time the agent writes or edits an `.html` file — no extra tool call, no round-trip, it just happens.

- **`/codeweb on` / `/codeweb off`** — one of the few slash commands whitelisted to run from the web client itself (see Local Web UI above); switches the session to a dedicated `codeweb` agent with its own system prompt, independent from the `build`/`plan` prompt.
- **Sandboxed dry-run before swap** — every auto-preview first loads in a hidden sandbox `iframe`; only if it loads without a runtime error (or unhandled promise rejection, or unexpected navigation) does the visible pane switch to it. A broken save never overwrites a working preview.
- **Live DOM patching, not a hard reload** — editing the file currently being previewed patches the running DOM in place instead of reloading, so scroll position and JS state survive small edits; changed nodes get a brief highlight flash so you can see what moved.
- **Multi-file tabs** — every `.html` file that has passed a preview check gets its own tab; switching tabs is instant (no re-run needed).
- **Internal dev servers open inline** — if the agent starts a real server (via the special `serve:` bash prefix, since a normal `bash` call can't run a long-lived process) and reports a `localhost`/private-IP URL, clicking that link in the chat opens it as a live tab in the same preview pane instead of leaving the app.
- **Resizable, ratio-constrained viewport** — drag the divider to resize the two columns, or lock the preview frame to a fixed aspect ratio (16:9, 9:16, 4:3, 1:1, 20:9) to simulate a specific device/viewport.
- **Read-only for the model** — the agent never sees the rendered page or a screenshot of it; it only knows whether its own save passed or failed the sandbox check. Actual visual confirmation always comes from you.

```
/codeweb on
# → dedicated system prompt + two-column layout (progress | live preview) enabled
```

> Implemented in `13_codeweb.py` (agent/system prompt/auto-preview hook) and the `codeweb*` functions in `web_index.html` (sandbox check, DOM morph, tabs, resizable split). Only meaningful while `/web` is armed — typing it from the real terminal has no effect.

---

### Skill System

On-demand domain guidance the model can pull in mid-task via the `skill` tool, instead of bloating the system prompt with instructions it may never need.

- **Read-only, on-demand loading** — the model calls `skill("name")`, which reads a `SKILL.md` file and returns its content as the tool result. Nothing is auto-injected into context until asked for.
- **Search paths** (checked in order):
  - `.fw_data/skills/` — project-local (primary)
  - `.opencode/skills/` — opencode compatibility
- **Flexible name resolution** — `skill("python")` matches `python`, `python.md`, `python/SKILL.md`, `PYTHON/SKILL.md`, or `python.skill.md`, whichever exists first.
- **Self-discovering** — an unknown skill name doesn't just fail; the tool result lists every skill it *did* find, so the model can self-correct without a separate "list skills" round trip.
- **`/skills`** — lists all available skills from the terminal at any time.

```bash
mkdir -p .fw_data/skills/my-skill
echo "---
name: my-skill
description: When to use this skill.
---
Instructions go here." > .fw_data/skills/my-skill/SKILL.md
```

> Implemented in `tool_skill()` (`07_tools_more.py`) and `SKILLS_DIRS` (`04_agent_cache.py`). Compatible with the community `SKILL.md` format used by Claude Code, Codex, and opencode.

---

### API Key Pool & Rotation

Each provider can hold **multiple API keys** instead of just one. When a request hits HTTP 429 (rate limit / quota), the pool puts that key on cooldown and automatically retries with a different key from the same provider — no blind sleep-and-hope if a free key is available.

- **429 vs 5xx are handled differently.** 429 means *that key* is limited, so the pool rotates to another key. 5xx means the *provider/server* is having issues — every key would hit the same error, so rotation is skipped and the existing sleep-with-backoff retry runs instead, on the same key.
- **Two rotation strategies**, selectable per provider: `round_robin` (always pick the key that's been idle longest) and `fill_first` (prefer the key with the fewest recent failures).
- **Cooldown is dynamic.** If the 429 response includes `Retry-After`, that value is used; otherwise a default cooldown applies. If every key in the pool is on cooldown, the CLI waits only as long as the soonest key needs, not a fixed delay.
- **Successful calls decay `fail_count`** on the key that was used, so a key that failed once but works again gradually returns to normal priority.
- **Backward compatible.** If you've only ever set a single key (`/setkey` or the provider's env var), the pool lazily treats it as a 1-key pool the first time it's needed — no migration step required.
- **Keys are always masked** in terminal output (e.g. `fw-abc1...ef92`), never printed in full.

| Command | Effect |
|---|---|
| `/addkey <key>` | Add another key to the current provider's pool |
| `/listkeys` | List all keys in the pool with cooldown status |
| `/rmkey <n>` | Remove a key by its `/listkeys` index |
| `/keystrategy <round_robin\|fill_first>` | Switch rotation strategy |

> Implemented in `11_key_pool.py`, wired into the retry loop in `09_api_system.py`. Model selection is unaffected by key rotation — only the `Authorization`/`x-api-key` credential changes between attempts.

---

### Project Structure

```
fw.py                        # Entry point / module loader
.fw_data/src/
├── 01_ui.py                 # Terminal UI components
├── 01b_aws.py                # AWS Bedrock Converse adapter
├── 01c_anthropic.py          # Anthropic Messages API adapter
├── 01d_events.py             # EventBus, ask()/PendingAsk, CLI+Web renderers, web input bridge
├── 01e_openai_responses.py   # OpenAI Responses API (/v1/responses) adapter
├── 02_provider.py           # Provider registry & API config
├── 03_mcp.py                # MCP integration
├── 04_agent_cache.py        # Permissions, file cache, sandbox
├── 05_session_db.py         # SQLite session persistence, tool schemas
├── 06_tools_fs.py           # File system tools
├── 07_tools_more.py         # Extended tools (web, todo, lsp, etc.)
├── 08_undo_dispatch.py      # Undo/redo + subagent dispatch
├── 09_api_system.py         # API streaming, system prompt, agentic loop
├── 11_key_pool.py           # Multi-key pool, 429 rotation, cooldown
├── 12_web.py                # Local Web UI — stdlib WebSocket bridge to the running session
├── 13_codeweb.py            # /codeweb agent, system prompt, sandboxed auto-preview hook
├── web_index.html           # /web frontend — chat UI, live preview pane, WebSocket client
└── 10_main.py               # Main CLI entrypoint, REPL, slash commands
```

> All modules `exec()` into a single shared namespace — no internal imports. See `fw.py` header comments for why module order matters.

---

### Requirements

- Python 3.10+
- No third-party packages required for core functionality
- An API key for at least one supported provider

---

### Quick Start

**Install via pip (recommended):**

```bash
git clone https://github.com/phiiggfdg/Open-cli-codex.git
cd Open-cli-codex
pip install .
```

Then run from anywhere:

```bash
opencli
```

**Or run directly:**

```bash
# Set your provider API key (example: Fireworks AI)
export FIREWORKS_API_KEY="your_key_here"

python fw.py
```

---

### Disclaimer

**This software is provided "as is", without warranty of any kind, express or implied.**

The author makes no representations or warranties regarding the accuracy, reliability, completeness, or suitability of this software for any purpose. Use of this software is entirely at your own risk.

The author shall not be held liable for any damages, data loss, unintended behavior, security vulnerabilities, or other consequences arising from the use or misuse of this software.

This project was built for personal use and experimentation. It is not production-ready and has not undergone formal security auditing.

---

### Security & Terms of Use

<details>
<summary><strong>API Keys & Credentials</strong></summary>

- Never commit API keys, tokens, or credentials to version control.
- This software may send data to third-party AI provider APIs (Fireworks AI, Cohere, Cerebras, Mistral, NVIDIA NIM, AWS Bedrock, and others — see [Supported Providers](#supported-providers)). Review each provider's privacy policy before use.
- The author is not responsible for any data transmitted to external services through the use of this software.

</details>

<details>
<summary><strong>Network & System Access</strong></summary>

- This software can execute shell commands (`bash` tool) and read/write files on your system. Use with caution and review all tool calls before execution in sensitive environments.
- The author is not responsible for any damage to systems, data, or infrastructure resulting from the use of this software.

</details>

<details>
<summary><strong>Security Vulnerabilities</strong></summary>

- This software has not been audited for security. Do not use it in production environments or expose it to untrusted inputs without proper sandboxing.
- If you discover a security issue, please contact the author privately before public disclosure.

</details>

---

### Data, Prompts & Intellectual Property

**All data, system prompts, prompt engineering patterns, and configurations included in this repository are the intellectual property of Trần Tuấn Phi.**

The following restrictions apply:

- **Public sharing or internet publication** of any data, prompts, prompt configurations, or design patterns from this project **requires explicit written permission** from the author.
- **Commercial use of any kind** — including but not limited to selling, sublicensing, incorporating into paid products or services, or using for profit — is **strictly prohibited** without prior written consent from the author.
- You may use this software for personal, educational, or non-commercial research purposes, provided that proper attribution is given.
- Derivative works that modify or extend this project must not be distributed commercially without permission.

To request permission: **phihhhhhhhhhh@gmail.com**

---

### License

This project does **not** use a standard open-source license. All rights are reserved by the author unless explicitly stated otherwise.

Permission is granted to:
- View and study the source code for personal learning
- Fork and modify privately for non-commercial use
- Share with attribution for non-commercial educational purposes

Permission is **NOT** granted to:
- Use commercially in any form without written consent
- Publish, redistribute, or sublicense the code or prompts publicly without permission
- Remove or alter this copyright notice or attribution

---

### Contact

**Author:** Trần Tuấn Phi
**Nationality:** Vietnamese 🇻🇳
**Email:** [phihhhhhhhhhh@gmail.com](mailto:phihhhhhhhhhh@gmail.com)
**Facebook:** [https://www.facebook.com/share/1EP6H8S25B/](https://www.facebook.com/share/1EP6H8S25B/)

<div align="right">

[⬆ back to top](#table-of-contents)

</div>

---
---

## 🇻🇳 Tiếng Việt

### Quyền sở hữu

> **Dự án này — bao gồm toàn bộ mã nguồn, system prompt, các mẫu kỹ thuật prompt, cấu hình và các quyết định thiết kế — là tài sản trí tuệ độc quyền của Trần Tuấn Phi.**
>
> Bảo lưu mọi quyền. Nghiêm cấm mọi hình thức sử dụng thương mại, phân phối lại hoặc đăng tải công khai khi chưa được phép.

---

### Được xây dựng với sự hỗ trợ của AI

Dự án này được thiết kế, kiến trúc và xây dựng bởi **Trần Tuấn Phi**. Các công cụ AI được sử dụng như trợ lý lập trình trong quá trình phát triển:

| Trợ lý AI | Vai trò |
|---|---|
| **Claude** (Anthropic) | Trợ lý lập trình chính — kiến trúc, logic, kỹ thuật system prompt |
| **ChatGPT** (OpenAI) | Phân tích đối chiếu và xác minh chéo |
| **Gemini** (Google) | Tham khảo bổ sung và review |

> Toàn bộ prompt, quyết định kiến trúc, thiết kế công cụ và định hướng sáng tạo đều xuất phát từ và là tài sản của **Trần Tuấn Phi**. Các trợ lý AI chỉ được sử dụng như công cụ — chúng không có bất kỳ quyền sở hữu nào đối với dự án này.

---

### Giới thiệu

`fw.py` là một CLI agent AI viết bằng Python thuần túy, được xây dựng từ đầu phục vụ mục đích cá nhân. Công cụ này kết nối với nhiều nhà cung cấp AI — qua các định dạng OpenAI-compatible, Anthropic Messages API, và AWS Bedrock Converse — thông qua một định dạng tin nhắn nội bộ thống nhất, hỗ trợ vòng lặp agent đầy đủ với khả năng sử dụng công cụ, lưu trữ phiên bằng SQLite, và giao diện terminal hiện đại.

Dự án được phát triển như một công cụ cá nhân và chỉ được chia sẻ công khai cho mục đích tham khảo và học tập.

---

### Tính năng

<details open>
<summary><strong>Năng lực cốt lõi</strong></summary>

- **Engine đa định dạng** — OpenAI-compatible, Anthropic Messages API, AWS Bedrock Converse, tất cả được chuẩn hoá về 1 dạng tin nhắn nội bộ duy nhất
- **Vòng lặp agent** hỗ trợ gọi tool song song, tối ưu prompt-cache, tự động tiếp tục khi output bị cắt
- **Pool nhiều API key, tự động xoay** — thêm nhiều key cho cùng 1 provider; khi dính HTTP 429, pool cho key đó nghỉ (cooldown) và chuyển sang key khác đang rảnh thay vì ngồi chờ vô ích
- **Quản lý phiên bằng SQLite** với tự động nén context tại ~80k token
- **Tích hợp MCP** (Model Context Protocol)
- **Hệ thống skill** — load `SKILL.md` theo yêu cầu qua tool `skill`, chỉ nạp khi cần (tương thích layout `.opencode/skills`)
- **Web UI local** (`/web`) — bridge WebSocket không cần thư viện ngoài, phản chiếu phiên CLI đang chạy ra trình duyệt, không spawn tiến trình riêng
- **Thực thi trong sandbox** — mỗi phiên chạy trong thư mục làm việc riêng biệt, cô lập
- **Hệ thống undo/redo** cho các thao tác sửa file
- **Hỗ trợ extended thinking / reasoning** (Claude extended thinking, DeepSeek-style reasoning) với cơ chế replay đúng round-trip
- **Giao diện terminal hiện đại** — banner gradient, spinner braille, thanh context gradient
- **Không phụ thuộc thư viện bên ngoài** — chỉ cần Python chuẩn để chạy phần lõi

</details>

<details>
<summary><strong>Tại sao lại cần 1 engine đa định dạng riêng?</strong></summary>

Phần lớn CLI agent chỉ hỗ trợ 1 dạng API duy nhất. `fw.py` nội bộ chỉ "nói" 1 ngôn ngữ — định dạng OpenAI chat-completions — 2 module adapter dịch 2 chiều sang Anthropic Messages API và AWS Bedrock Converse (bao gồm cả việc tự parse binary event-stream của Bedrock), nên toàn bộ tool, prompt, và vòng lặp agent chỉ cần viết 1 lần duy nhất mà vẫn chạy giống hệt nhau trên cả 12 provider.

</details>

---

### Nhà cung cấp được hỗ trợ

12 provider có sẵn ngay khi cài đặt. Bạn cũng có thể thêm **bất kỳ** endpoint nào tương thích OpenAI hoặc theo định dạng Anthropic thông qua wizard cài đặt trong app.

| # | Nhà cung cấp | Biến môi trường |
|---|---|---|
| 1 | Fireworks AI | `FIREWORKS_API_KEY` |
| 2 | Cohere | `COHERE_API_KEY` |
| 3 | Cerebras | `CEREBRAS_API_KEY` |
| 4 | Mistral AI | `MISTRAL_API_KEY` |
| 5 | NVIDIA NIM | `NVIDIA_API_KEY` |
| 6 | Command Code | `COMMANDCODE_API_KEY` |
| 7 | Xiaomi (MiMo) | `MIMO_API_KEY` |
| 8 | Qwen API (Singapore / DashScope) | `DASHSCOPE_API_KEY` |
| 9 | Mercury 2 (Inception Labs) | `INCEPTION_API_KEY` |
| 10 | Mara Cloud | `MARA_API_KEY` |
| 11 | Requesty AI | `REQUESTY_API_KEY` |
| 12 | AWS Bedrock (Converse API) | `AWS_BEDROCK_API_KEY` |

> Ngoài ra: **wizard thêm provider tuỳ chỉnh** — thêm bất kỳ endpoint OpenAI-compatible hoặc Anthropic-format (`format_anthropic=True`) nào ngay khi đang chạy, không cần sửa code.

---

### Công cụ của agent

<details open>
<summary><strong>21 tool tích hợp sẵn</strong> (bấm để xem theo nhóm)</summary>

| Nhóm | Tools |
|---|---|
| **Shell** | `bash` |
| **Đọc/ghi file** | `read`, `write`, `edit`, `multiedit`, `extract`, `apply_patch` |
| **Tìm kiếm** | `glob`, `grep`, `view_symbol`, `file_index` |
| **Web** | `webfetch`, `websearch` |
| **Lập kế hoạch** | `todowrite`, `todoread`, `question`, `verify` |
| **Code intelligence** | `lsp` |
| **Điều phối** | `task` (gọi subagent), `skill` |

</details>

---

### Web UI local (`/web`)

Gõ `/web` trong CLI đang chạy để mở bridge trình duyệt local — **không spawn tiến trình con nào cả**. Tab trình duyệt kết nối qua WebSocket vào đúng `SessionState` mà CLI đang dùng (chung messages, chung model, chung context).

- **Không cần thư viện ngoài** — WebSocket server (handshake RFC 6455, đóng gói frame) tự viết trên nền `http.server`/`socketserver`, không cần Flask/FastAPI/websockets.
- **Bàn phím CLI khoá khi đang armed** — input được đọc từ trình duyệt thay vì bàn phím thật; bấm `Esc` (hoặc `Ctrl-C`) trên terminal thật để lấy lại quyền ngay lập tức. Web server vẫn chạy nền dù đang ở chế độ nào.
- **Phản chiếu event trực tiếp** — mọi `Event` phiên phát ra (text streaming, tool call, kết quả tool, thinking, todo update) được đẩy qua trình duyệt dạng JSON theo thời gian thực, không phải replay byte-stream terminal thô.
- **Lệnh slash chỉ dùng được trên CLI thật, có chủ đích** — gõ `/lệnh` hoặc `exit`/`quit`/`q` từ web client sẽ bị từ chối kèm cảnh báo; Web UI dùng để chat và xem agent làm việc, không phải để điều khiển REPL. Quay lại terminal thật (`Esc`) để chạy lệnh.
- **Chỉ 1 session hoạt động tại 1 thời điểm** — web bridge luôn phản chiếu đúng `SessionState` đang được đăng ký là session của CLI (vd đổi session qua `/sessions` sẽ tự động trỏ lại bridge).
- **Hỗ trợ gửi ảnh** — đính kèm ảnh trực tiếp từ trình duyệt; chỉ `/web` mới gửi được ảnh (bàn phím CLI thật không có đường nào làm việc này). Mỗi ảnh gửi lên được kiểm tra ở phía server trước khi đưa vào turn: định dạng MIME không hỗ trợ sẽ bị bỏ qua kèm cảnh báo, ảnh base64 quá lớn (ảnh full-res chưa resize) bị chặn kèm giới hạn cụ thể, tối đa 6 ảnh mỗi lượt. Frontend cũng tự nhớ theo từng model đã biết hỗ trợ ảnh hay chưa, thay vì luôn mở khoá nút gửi ảnh một cách mù quáng.

```
/web
# → Web UI đang chạy: http://127.0.0.1:8765/
# → Ô nhập CLI tạm khoá — thao tác trên trình duyệt.
# → Nhấn Esc để quay lại CLI (web server vẫn chạy nền).
```

> Cài đặt tại `12_web.py`. Ghi chú kiến trúc: bản thiết kế cũ (spawn PTY, trình duyệt chỉ là terminal emulator xem lại byte ANSI) đã được thay bằng bridge `EventBus` trực tiếp này, để trình duyệt hiển thị được tool card/JSON có cấu trúc thay vì byte ANSI thô.

---

### Mode Codeweb (`/codeweb`)

Mode phụ của `/web`, thiết kế riêng cho công việc frontend: layout 2 cột, bên trái vẫn là log chat/tool như bình thường, bên phải là **panel xem trước trực tiếp** (live preview), tự động cập nhật mỗi khi agent ghi hoặc sửa 1 file `.html` — không cần gọi thêm tool, không round-trip, tự động xảy ra.

- **`/codeweb on` / `/codeweb off`** — một trong số ít lệnh slash được whitelist chạy được ngay từ web client (xem mục Web UI local ở trên); chuyển session sang agent `codeweb` riêng, dùng system prompt độc lập, tách biệt hoàn toàn khỏi prompt `build`/`plan`.
- **Chạy thử trong sandbox trước khi thay thế** — mỗi lần auto-preview, nội dung được nạp thử vào 1 `iframe` sandbox ẩn trước; chỉ khi nạp xong không có lỗi runtime (hoặc unhandled promise rejection, hoặc điều hướng bất thường) thì panel hiển thị mới chuyển sang nội dung đó. File lưu bị lỗi sẽ không bao giờ đè lên bản preview đang chạy tốt.
- **Vá trực tiếp vào DOM đang sống, không reload cứng** — sửa đúng file đang được xem sẽ patch thẳng vào DOM đang chạy thay vì tải lại từ đầu, nên vị trí cuộn và state JS vẫn giữ nguyên qua các lần sửa nhỏ; các node vừa đổi được highlight chớp nhẹ để dễ nhận ra chỗ vừa thay đổi.
- **Nhiều tab file** — mỗi file `.html` đã pass kiểm tra preview có 1 tab riêng; chuyển tab tức thì, không cần chạy lại.
- **Server nội bộ mở ngay trong app** — nếu agent khởi động 1 server thật (qua tiền tố `serve:` đặc biệt của `bash`, vì `bash` thường không chạy được tiến trình sống lâu) và báo địa chỉ `localhost`/IP nội bộ, bấm vào link đó trong chat sẽ mở ngay thành 1 tab preview sống trong cùng panel, thay vì rời khỏi app.
- **Khung xem đổi được kích thước, khoá theo tỉ lệ** — kéo thanh chia để đổi kích thước 2 cột, hoặc khoá khung preview theo tỉ lệ cố định (16:9, 9:16, 4:3, 1:1, 20:9) để mô phỏng 1 thiết bị/viewport cụ thể.
- **Model không tự xem được kết quả** — agent không bao giờ thấy trang đã render hay ảnh chụp của nó; chỉ biết lần lưu của chính mình có pass hay fail kiểm tra sandbox. Xác nhận trực quan thật sự luôn đến từ bạn.

```
/codeweb on
# → system prompt riêng + layout 2 cột (tiến trình | live preview) đã bật
```

> Cài đặt tại `13_codeweb.py` (agent/system prompt/hook auto-preview) và các hàm `codeweb*` trong `web_index.html` (kiểm tra sandbox, morph DOM, quản lý tab, chia cột đổi kích thước được). Chỉ có ý nghĩa khi `/web` đang armed — gõ lệnh này từ terminal thật không có tác dụng gì.

---

### Hệ thống Skill

Kiến thức chuyên biệt theo domain, model tự gọi giữa lúc làm việc qua tool `skill`, thay vì nhồi hết vào system prompt những thứ chưa chắc dùng đến.

- **Chỉ đọc, nạp theo yêu cầu** — model gọi `skill("tên")`, đọc file `SKILL.md` và trả nội dung về làm kết quả tool. Không có gì tự động bơm vào context nếu không được yêu cầu.
- **Đường dẫn tìm kiếm** (theo thứ tự):
  - `.fw_data/skills/` — project-local (chính)
  - `.opencode/skills/` — tương thích opencode
- **Linh hoạt khi tìm tên** — `skill("python")` khớp với `python`, `python.md`, `python/SKILL.md`, `PYTHON/SKILL.md`, hoặc `python.skill.md`, tuỳ cái nào tồn tại trước.
- **Tự gợi ý khi không tìm thấy** — gọi sai tên không chỉ báo lỗi; kết quả tool liệt kê luôn mọi skill đang có, để model tự sửa mà không cần gọi thêm 1 lượt "liệt kê skill" riêng.
- **`/skills`** — liệt kê toàn bộ skill hiện có từ terminal bất cứ lúc nào.

```bash
mkdir -p .fw_data/skills/my-skill
echo "---
name: my-skill
description: Khi nào nên dùng skill này.
---
Nội dung hướng dẫn ở đây." > .fw_data/skills/my-skill/SKILL.md
```

> Cài đặt tại `tool_skill()` (`07_tools_more.py`) và `SKILLS_DIRS` (`04_agent_cache.py`). Tương thích định dạng `SKILL.md` cộng đồng, dùng chung với Claude Code, Codex, và opencode.

---

### Pool API Key & Cơ chế xoay key

Mỗi provider có thể lưu **nhiều API key** thay vì chỉ 1. Khi request dính HTTP 429 (rate-limit/hết quota), pool cho key đó nghỉ (cooldown) và tự động thử lại bằng key khác cùng provider — không ngồi chờ vô ích nếu vẫn còn key rảnh.

- **Phân biệt rõ 429 và lỗi 5xx.** 429 nghĩa là *key đó* bị giới hạn → pool xoay sang key khác. 5xx nghĩa là *server/provider* đang lỗi → mọi key gọi vào đều dính y hệt, xoay key vô nghĩa, nên nhánh này giữ nguyên cơ chế cũ (chờ rồi thử lại với backoff, dùng lại đúng key đó).
- **2 chiến lược xoay key**, chọn riêng theo từng provider: `round_robin` (luôn ưu tiên key lâu chưa dùng nhất) và `fill_first` (ưu tiên key ít lỗi gần đây nhất).
- **Cooldown tính động.** Nếu response 429 có kèm `Retry-After`, dùng đúng giá trị đó; nếu không có thì dùng cooldown mặc định. Nếu toàn bộ key trong pool đều đang cooldown, CLI chỉ chờ đúng bằng thời gian key gần rảnh nhất cần, không chờ 1 khoảng cố định.
- **Gọi thành công sẽ giảm dần `fail_count`** của key vừa dùng — key từng lỗi 1 lần nhưng sau đó chạy ổn sẽ dần quay lại mức ưu tiên bình thường.
- **Tương thích ngược hoàn toàn.** Nếu bạn chỉ từng đặt 1 key duy nhất (qua `/setkey` hoặc biến môi trường của provider), lần đầu cần dùng pool sẽ tự coi key đơn đó là pool 1 phần tử — không cần thao tác migrate thủ công.
- **Key luôn được che khi hiển thị** ở terminal (vd `fw-abc1...ef92`), không bao giờ in đầy đủ.

| Lệnh | Tác dụng |
|---|---|
| `/addkey <key>` | Thêm 1 key vào pool của provider đang dùng |
| `/listkeys` | Xem toàn bộ key trong pool kèm trạng thái cooldown |
| `/rmkey <n>` | Xoá key theo số thứ tự hiển thị ở `/listkeys` |
| `/keystrategy <round_robin\|fill_first>` | Đổi chiến lược xoay key |

> Cài đặt tại `11_key_pool.py`, được gắn vào vòng lặp retry trong `09_api_system.py`. Việc xoay key không ảnh hưởng tới model đã chọn — chỉ thay đổi credential (`Authorization`/`x-api-key`) giữa các lần thử.

---

### Cấu trúc dự án

```
fw.py                        # Điểm khởi chạy / loader module
.fw_data/src/
├── 01_ui.py                 # Giao diện terminal
├── 01b_aws.py                # Adapter AWS Bedrock Converse
├── 01c_anthropic.py          # Adapter Anthropic Messages API
├── 01d_events.py             # EventBus, ask()/PendingAsk, renderer CLI+Web, web input bridge
├── 01e_openai_responses.py   # Adapter OpenAI Responses API (/v1/responses)
├── 02_provider.py           # Registry & cấu hình nhà cung cấp
├── 03_mcp.py                # Tích hợp MCP
├── 04_agent_cache.py        # Permission, file cache, sandbox
├── 05_session_db.py         # Lưu phiên bằng SQLite, schema tool
├── 06_tools_fs.py           # Công cụ file system
├── 07_tools_more.py         # Công cụ mở rộng (web, todo, lsp...)
├── 08_undo_dispatch.py      # Undo/redo + dispatch subagent
├── 09_api_system.py         # Streaming API, system prompt, vòng lặp agent
├── 11_key_pool.py           # Pool nhiều key, xoay key khi 429, cooldown
├── 12_web.py                # Web UI local — bridge WebSocket stdlib tới phiên đang chạy
├── 13_codeweb.py            # Agent /codeweb, system prompt riêng, hook auto-preview sandbox
├── web_index.html           # Frontend /web — giao diện chat, panel live preview, WebSocket client
└── 10_main.py               # Entrypoint CLI chính, REPL, slash command
```

> Tất cả module được `exec()` vào chung 1 namespace — không có import nội bộ giữa các file. Xem comment đầu `fw.py` để hiểu vì sao thứ tự module quan trọng.

---

### Yêu cầu

- Python 3.10 trở lên
- Không cần cài thêm thư viện ngoài cho phần lõi
- API key từ ít nhất một nhà cung cấp được hỗ trợ

---

### Hướng dẫn nhanh

**Cài đặt qua pip (khuyến nghị):**

```bash
git clone https://github.com/phiiggfdg/Open-cli-codex.git
cd Open-cli-codex
pip install .
```

Sau đó chạy từ bất kỳ đâu:

```bash
opencli
```

**Hoặc chạy trực tiếp:**

```bash
# Cài đặt API key (ví dụ: Fireworks AI)
export FIREWORKS_API_KEY="your_key_here"

python fw.py
```

---

### Miễn trừ trách nhiệm

**Phần mềm này được cung cấp "nguyên trạng", không có bất kỳ bảo đảm nào, dù rõ ràng hay ngụ ý.**

Tác giả không chịu trách nhiệm về tính chính xác, độ tin cậy, tính đầy đủ hay sự phù hợp của phần mềm này cho bất kỳ mục đích nào. Việc sử dụng phần mềm này hoàn toàn là rủi ro của người dùng.

Tác giả không chịu trách nhiệm về bất kỳ thiệt hại, mất mát dữ liệu, hành vi ngoài ý muốn, lỗ hổng bảo mật hay hậu quả nào khác phát sinh từ việc sử dụng hoặc lạm dụng phần mềm này.

Dự án này được xây dựng cho mục đích cá nhân và thử nghiệm. Nó không sẵn sàng cho môi trường production và chưa được kiểm tra bảo mật chính thức.

---

### Bảo mật & Điều khoản sử dụng

<details>
<summary><strong>API Key & Thông tin xác thực</strong></summary>

- Không bao giờ đưa API key, token hay thông tin xác thực vào version control.
- Phần mềm này có thể gửi dữ liệu đến API của các nhà cung cấp AI bên thứ ba (Fireworks AI, Cohere, Cerebras, Mistral, NVIDIA NIM, AWS Bedrock, và nhiều hãng khác — xem [Nhà cung cấp được hỗ trợ](#nhà-cung-cấp-được-hỗ-trợ)). Hãy đọc chính sách bảo mật của từng nhà cung cấp trước khi sử dụng.
- Tác giả không chịu trách nhiệm về bất kỳ dữ liệu nào được truyền đến các dịch vụ bên ngoài thông qua việc sử dụng phần mềm này.

</details>

<details>
<summary><strong>Truy cập mạng & Hệ thống</strong></summary>

- Phần mềm này có khả năng thực thi lệnh shell (`bash` tool) và đọc/ghi file trên hệ thống của bạn. Hãy cẩn thận và xem xét tất cả các lệnh trước khi thực thi trong môi trường nhạy cảm.
- Tác giả không chịu trách nhiệm về bất kỳ hư hại nào đối với hệ thống, dữ liệu hay cơ sở hạ tầng do sử dụng phần mềm này.

</details>

<details>
<summary><strong>Lỗ hổng bảo mật</strong></summary>

- Phần mềm này chưa được kiểm tra bảo mật. Không sử dụng trong môi trường production hoặc với dữ liệu đầu vào không đáng tin cậy nếu không có sandbox phù hợp.
- Nếu phát hiện vấn đề bảo mật, vui lòng liên hệ tác giả riêng tư trước khi công bố công khai.

</details>

---

### Dữ liệu, Prompt & Quyền sở hữu trí tuệ

**Toàn bộ dữ liệu, system prompt, các mẫu kỹ thuật prompt và cấu hình trong repository này là tài sản trí tuệ của Trần Tuấn Phi.**

Các hạn chế sau đây được áp dụng:

- **Chia sẻ công khai hoặc đăng tải lên internet** bất kỳ dữ liệu, prompt, cấu hình prompt hay mẫu thiết kế nào từ dự án này **đều yêu cầu sự cho phép bằng văn bản rõ ràng** từ tác giả.
- **Mọi hình thức sử dụng thương mại** — bao gồm nhưng không giới hạn ở việc bán, cấp phép lại, tích hợp vào sản phẩm/dịch vụ có thu phí, hay sử dụng vì lợi nhuận — **bị nghiêm cấm hoàn toàn** khi chưa có sự đồng ý bằng văn bản từ tác giả.
- Bạn có thể sử dụng phần mềm này cho mục đích cá nhân, giáo dục hoặc nghiên cứu phi thương mại, với điều kiện ghi rõ nguồn gốc và tác giả.
- Các tác phẩm phái sinh chỉnh sửa hoặc mở rộng dự án này không được phân phối thương mại khi chưa có phép.

Để xin phép: **phihhhhhhhhhh@gmail.com**

---

### Giấy phép

Dự án này **không** sử dụng giấy phép mã nguồn mở tiêu chuẩn. Mọi quyền đều được tác giả bảo lưu trừ khi có quy định rõ ràng khác.

Được phép:
- Xem và nghiên cứu mã nguồn cho mục đích học tập cá nhân
- Fork và chỉnh sửa riêng tư cho mục đích phi thương mại
- Chia sẻ có ghi nguồn cho mục đích giáo dục phi thương mại

**Không được phép:**
- Sử dụng thương mại dưới bất kỳ hình thức nào khi chưa có sự đồng ý bằng văn bản
- Xuất bản, phân phối lại hoặc cấp phép lại mã nguồn hay prompt công khai khi chưa có phép
- Xóa hoặc thay đổi thông báo bản quyền hay thông tin tác giả này

---

### Liên hệ

**Tác giả:** Trần Tuấn Phi
**Quốc tịch:** Việt Nam 🇻🇳
**Email:** [phihhhhhhhhhh@gmail.com](mailto:phihhhhhhhhhh@gmail.com)
**Facebook:** [https://www.facebook.com/share/1EP6H8S25B/](https://www.facebook.com/share/1EP6H8S25B/)

<div align="right">

[⬆ về đầu trang](#table-of-contents)

</div>

---

<div align="center">

*© 2024–2026 Trần Tuấn Phi. All rights reserved. / Bảo lưu mọi quyền.*

</div>
