# fw.py — Python CLI Coding Agent

> A lightweight, stdlib-only Python CLI agent supporting multiple AI providers with session management, tool dispatch, and an agentic loop.

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

`fw.py` is a personal Python CLI coding agent built from scratch. It connects to multiple AI providers via OpenAI-compatible endpoints and supports an agentic loop with tool use, SQLite-based session persistence, and a modern terminal UI.

This project was developed as a personal tool and is shared publicly for reference and learning purposes only.

---

### Features

- Multi-provider support: Fireworks AI, Mistral, NVIDIA NIM, and any OpenAI-compatible endpoint
- Agentic loop with tool dispatch: `bash`, `read`, `write`, `edit`, `glob`, `grep`, `webfetch`, `websearch`, `todowrite`, `todoread`, `question`, `apply_patch`, `task`
- SQLite session management with automatic context compaction at ~80k tokens
- MCP (Model Context Protocol) integration
- Modern terminal UI: gradient banners, braille spinners, gradient context bars
- Undo/redo dispatch system
- File system tools with safe read/write operations
- Stdlib-only core — no heavyweight dependencies

---

### Project Structure

```
fw.py                        # Entry point
.fw_data/src/
├── 01_ui.py                 # Terminal UI components
├── 02_provider.py           # Provider registry & API config
├── 03_mcp.py                # MCP integration
├── 04_agent_cache.py        # Agent loop & cache management
├── 05_session_db.py         # SQLite session persistence
├── 06_tools_fs.py           # File system tools
├── 07_tools_more.py         # Extended tools (web, todo, etc.)
├── 08_undo_dispatch.py      # Undo/redo dispatch
├── 09_api_system.py         # API & system prompt
└── 10_main.py               # Main CLI entrypoint
```

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

**API Keys & Credentials**

- Never commit API keys, tokens, or credentials to version control.
- This software may send data to third-party AI provider APIs (Fireworks AI, Mistral, NVIDIA NIM, etc.). Review each provider's privacy policy before use.
- The author is not responsible for any data transmitted to external services through the use of this software.

**Network & System Access**

- This software can execute shell commands (`bash` tool) and read/write files on your system. Use with caution and review all tool calls before execution in sensitive environments.
- The author is not responsible for any damage to systems, data, or infrastructure resulting from the use of this software.

**Security Vulnerabilities**

- This software has not been audited for security. Do not use it in production environments or expose it to untrusted inputs without proper sandboxing.
- If you discover a security issue, please contact the author privately before public disclosure.

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

`fw.py` là một CLI agent AI viết bằng Python thuần túy, được xây dựng từ đầu phục vụ mục đích cá nhân. Công cụ này kết nối với nhiều nhà cung cấp AI thông qua các endpoint tương thích OpenAI, hỗ trợ vòng lặp agent với khả năng sử dụng công cụ, lưu trữ phiên bằng SQLite, và giao diện terminal hiện đại.

Dự án được phát triển như một công cụ cá nhân và chỉ được chia sẻ công khai cho mục đích tham khảo và học tập.

---

### Tính năng

- Hỗ trợ nhiều nhà cung cấp: Fireworks AI, Mistral, NVIDIA NIM, và bất kỳ endpoint nào tương thích OpenAI
- Vòng lặp agent với điều phối công cụ: `bash`, `read`, `write`, `edit`, `glob`, `grep`, `webfetch`, `websearch`, `todowrite`, `todoread`, `question`, `apply_patch`, `task`
- Quản lý phiên bằng SQLite với tự động nén context tại ~80k token
- Tích hợp MCP (Model Context Protocol)
- Giao diện terminal hiện đại: banner gradient, spinner braille, thanh context gradient
- Hệ thống undo/redo
- Công cụ file system với thao tác đọc/ghi an toàn
- Không phụ thuộc vào thư viện bên ngoài (stdlib-only)

---

### Cấu trúc dự án

```
fw.py                        # Điểm khởi chạy chính
.fw_data/src/
├── 01_ui.py                 # Giao diện terminal
├── 02_provider.py           # Registry & cấu hình nhà cung cấp
├── 03_mcp.py                # Tích hợp MCP
├── 04_agent_cache.py        # Vòng lặp agent & quản lý cache
├── 05_session_db.py         # Lưu phiên bằng SQLite
├── 06_tools_fs.py           # Công cụ file system
├── 07_tools_more.py         # Công cụ mở rộng (web, todo...)
├── 08_undo_dispatch.py      # Undo/redo dispatch
├── 09_api_system.py         # API & system prompt
└── 10_main.py               # Entrypoint CLI chính
```

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

**API Key & Thông tin xác thực**

- Không bao giờ đưa API key, token hay thông tin xác thực vào version control.
- Phần mềm này có thể gửi dữ liệu đến API của các nhà cung cấp AI bên thứ ba (Fireworks AI, Mistral, NVIDIA NIM...). Hãy đọc chính sách bảo mật của từng nhà cung cấp trước khi sử dụng.
- Tác giả không chịu trách nhiệm về bất kỳ dữ liệu nào được truyền đến các dịch vụ bên ngoài thông qua việc sử dụng phần mềm này.

**Truy cập mạng & Hệ thống**

- Phần mềm này có khả năng thực thi lệnh shell (`bash` tool) và đọc/ghi file trên hệ thống của bạn. Hãy cẩn thận và xem xét tất cả các lệnh trước khi thực thi trong môi trường nhạy cảm.
- Tác giả không chịu trách nhiệm về bất kỳ hư hại nào đối với hệ thống, dữ liệu hay cơ sở hạ tầng do sử dụng phần mềm này.

**Lỗ hổng bảo mật**

- Phần mềm này chưa được kiểm tra bảo mật. Không sử dụng trong môi trường production hoặc với dữ liệu đầu vào không đáng tin cậy nếu không có sandbox phù hợp.
- Nếu phát hiện vấn đề bảo mật, vui lòng liên hệ tác giả riêng tư trước khi công bố công khai.

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

---

*© 2024–2026 Trần Tuấn Phi. All rights reserved. / Bảo lưu mọi quyền.*
