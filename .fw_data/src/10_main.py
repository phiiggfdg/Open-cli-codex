# ── Auto-rename session sau turn đầu tiên ────────────────────────────────────
def _auto_rename_session(conn, sid, messages, model, api_key):
    """
    Gọi AI đặt tên session ngắn (≤6 từ, tiếng Việt) dựa vào turn đầu tiên.
    Chỉ chạy khi session vẫn mang tên mặc định "Session MM-DD HH:MM".
    Non-blocking: dùng thread riêng để không làm chậm main loop.
    """
    row = conn.execute("SELECT title FROM session WHERE id=?", (sid,)).fetchone()
    if not row:
        return
    title = row["title"]
    # Chỉ rename nếu vẫn là tên mặc định
    if not re.match(r"^Session \d{2}-\d{2} \d{2}:\d{2}$", title):
        return
    # Lấy user message đầu tiên để đặt tên
    first_user = ""
    for m in messages:
        if m.get("role") == "user":
            c = m.get("content") or ""
            if isinstance(c, str) and not c.startswith("["):
                first_user = c[:300]
                break
    if not first_user:
        return

    def _do_rename():
        def _api_call():
            # retry_max=2 (KHÔNG phải 1): tác vụ phụ, không quan trọng, nên
            # tránh retry dài 5 lần (loop >90s khi bị 429 — bug gốc). Nhưng
            # retry_max=1 có bug đã xác nhận bằng trace code: điều kiện
            # "attempt < retries-1" trong _call_simple luôn False ngay lần
            # thử đầu tiên khi retries=1 (0 < 0 = False) → nhánh xoay key
            # pool (pool_rotate_after_429, KHÔNG sleep, gần như miễn phí về
            # thời gian) không bao giờ chạy được — auto-rename fail ngay cả
            # khi pool có key khác đang rảnh sẵn. retry_max=2 mở đúng 1 cơ
            # hội retry: 429 → thử key khác ngay nếu có (không sleep); hết
            # key rảnh hoặc 5xx → sleep tối đa _RETRY_DELAYS[0]=5s (không
            # phải 25-30s như các lần retry sau ở _RETRY_MAX=5) rồi bỏ cuộc.
            # silent=True: không print cảnh báo, tránh phá màn hình người
            # dùng đang gõ ở main thread (đây là thread nền).
            # check_cancel=True: nếu người dùng Ctrl+C, dừng ngay thay vì
            # chờ hết request/sleep hiện tại — kể cả sleep 5s ở trên vẫn bị
            # _cancel_bg.wait() cắt ngang ngay lập tức, không phá nguyên tắc.
            return _call_simple(
                [{"role": "user", "content":
                    f"Đặt tên ngắn (tối đa 5 từ tiếng Việt, không dấu chấm) "
                    f"cho cuộc hội thoại bắt đầu bằng:\n\n{first_user}\n\n"
                    f"Chỉ trả lời tên, không giải thích."}],
                model, api_key, retry_max=2, silent=True, check_cancel=True
            )
        try:
            # _do_rename() itself already runs in a daemon thread.  Do not
            # create a nested ThreadPoolExecutor here: its non-daemon worker
            # is joined by Python during interpreter shutdown, which can
            # turn a normal Ctrl-C into a traceback if the network call is
            # still pending.
            result = _api_call()
            if result.get("text") == "[cancelled]":
                return  # người dùng đã Ctrl+C — không lưu tên
            new_title = result.get("text", "").strip().strip('"').strip("'")
            # Sanity: không dài hơn 60 ký tự, không chứa newline
            new_title = new_title.splitlines()[0][:60].strip()
            if new_title:
                session_update(conn, sid, title=new_title)
        except Exception:
            pass  # silent fail — không quan trọng nếu rename lỗi

    # Clear cờ hủy trước khi start thread mới — cờ này có thể đã bị set bởi
    # Ctrl+C ở turn trước; nếu không clear, thread mới sẽ bị coi là "đã hủy"
    # ngay từ đầu và thoát không làm gì.
    _cancel_bg.clear()
    threading.Thread(target=_do_rename, daemon=True).start()


def _delete_session_project_dir(session: dict) -> bool:
    """Delete only the generated cwd/<sid> directory owned by a session."""
    raw = session.get("project_dir")
    sid = session.get("id", "")
    if not raw or not sid:
        return False
    path = Path(raw).expanduser().resolve()
    expected = (Path(session.get("directory") or Path.cwd()) / sid).resolve()
    if path != expected or path.name != sid:
        return False
    if path.is_dir():
        shutil.rmtree(path)
    return True


# ════════════════════════════════════════════════════════════════════════════

def _print_welcome_banner():
    """Hiển thị banner chào mừng lần đầu khởi động — chỉ gọi khi chưa có session nào."""
    import time as _time
    import random as _random

    _GLITCH_CHARS = "!@#$%^&*<>?/|\\[]{}~`±§"

    def _glitch_line(line: str, intensity: int = 3) -> str:
        """Corrupt ngẫu nhiên một vài ký tự trong line để tạo glitch."""
        if not line.strip():
            return line
        chars = list(line)
        # Chỉ corrupt ký tự printable, không đụng ANSI escape
        printable_idx = []
        in_esc = False
        for i, c in enumerate(chars):
            if c == "\033":
                in_esc = True
            elif in_esc and c == "m":
                in_esc = False
            elif not in_esc and c not in (" ", "\n"):
                printable_idx.append(i)
        for _ in range(min(intensity, len(printable_idx))):
            idx = _random.choice(printable_idx)
            chars[idx] = _random.choice(_GLITCH_CHARS)
        return "".join(chars)

    # ── ASCII art lines ───────────────────────────────────────────────────────
    raw_banner = [
        "",
        f"  {CYAN}{BOLD}  ___  ____  ____  _  _     ___  __    ____     ___  _____  ____  ____  _  _  {R}",
        f"  {CYAN}{BOLD} / __)(  _ \\( ___)( \\( )   / __)(  )  (_  _)   / __)(  _  )(  _ \\( ___)( \\/ ) {R}",
        f"  {TEAL}{BOLD}( (__  )___/ )__)  )  (   ( (__  )(__  _)(_   ( (__  )(_)(  )(_) ))__)  )  (  {R}",
        f"  {TEAL}{BOLD} \\___)(_)   (____)(_)\\_)   \\___)(____)(____) o  \\___)(_____)(__,_/(____)(_/\\_) {R}",
        "",
    ]
    n = len(raw_banner)

    # ── Phase 1: scanline sweep — dòng trắng quét xuống ──────────────────────
    SCAN = f"\033[38;5;231m"   # near-white scanline
    for sweep in range(n):
        # In lại toàn bộ banner, highlight dòng sweep
        sys.stdout.write(f"\033[{n}A\r") if sweep > 0 else None
        for i, line in enumerate(raw_banner):
            if i == sweep and line.strip():
                # Glitch nặng trong lúc scanline đi qua
                sys.stdout.write(_glitch_line(line, intensity=6) + "\n")
            else:
                sys.stdout.write(line + "\n")
        sys.stdout.flush()
        _time.sleep(0.045)

    # ── Phase 2: glitch burst — rung 4 lần rồi resolve về clean ─────────────
    for burst in range(4):
        sys.stdout.write(f"\033[{n}A\r")
        intensity = 5 - burst  # giảm dần → settle
        for line in raw_banner:
            corrupted = _glitch_line(line, intensity=intensity) if burst < 3 else line
            sys.stdout.write(corrupted + "\n")
        sys.stdout.flush()
        _time.sleep(0.07)

    # ── Phase 3: final clean render ───────────────────────────────────────────
    sys.stdout.write(f"\033[{n}A\r")
    for line in raw_banner:
        sys.stdout.write(line + "\n")
    sys.stdout.flush()
    _time.sleep(0.12)

    # ── Tagline typing effect — character by character ────────────────────────
    tagline_parts = [
        (TEAL,    "  ▸ "),
        (WHITE,   "Open Source  ·  "),
        (CYAN,    "Multi-Provider  ·  "),
        (YELLOW,  "Terminal AI Coding Agent"),
    ]
    for color, part in tagline_parts:
        for ch in part:
            sys.stdout.write(f"{color}{ch}{R}")
            sys.stdout.flush()
            _time.sleep(0.013)
    print()

    # ── Separator draw animation — line grows left→right ─────────────────────
    w = shutil.get_terminal_size((80, 20)).columns
    sep_w = min(w - 4, 72)
    print()
    sys.stdout.write("  ")
    for i in range(sep_w):
        sys.stdout.write(f"{GRAY}╌{R}")
        sys.stdout.flush()
        _time.sleep(0.008)
    print()

    # ── Info block — cascade fade-in, each row slides from left ──────────────
    info = [
        (TEAL,    "◈", "Project   ", "Open CLI Codex"),
        (GREEN,   "◈", "Author    ", "Trần Phi"),
        (YELLOW,  "◈", "Contact   ", "phihhhhhhhhhh@gmail.com"),
        (CYAN,    "◈", "Inspired  ", "opencode · claude-code · codex"),
    ]
    for color, icon, label, value in info:
        full = f"  {color}{icon}{R}  {DIM}{label}{R}{WHITE}{value}{R}"
        # Print ký tự nhanh nhưng có micro-delay tạo cảm giác "drop in"
        sys.stdout.write(f"\033[2m{' ' * 4}{R}")   # dim placeholder
        sys.stdout.write("\r")
        sys.stdout.flush()
        _time.sleep(0.04)
        print(full)
        _time.sleep(0.055)

    # ── Separator close ───────────────────────────────────────────────────────
    sys.stdout.write("  ")
    for i in range(sep_w):
        sys.stdout.write(f"{GRAY}╌{R}")
        sys.stdout.flush()
        _time.sleep(0.006)
    print()
    _time.sleep(0.12)

    # ── Ready message — typewriter với cursor blinking ────────────────────────
    ready = "  System ready. Start your session  ◆"
    print()
    for i, ch in enumerate(ready):
        # Cursor blink: hiện underscore lúc gõ
        sys.stdout.write(f"{TEAL}{ch}{R}")
        sys.stdout.flush()
        _time.sleep(0.018 if ch != " " else 0.009)
    # Blink ◆ 3 lần sau khi xong
    for _ in range(3):
        sys.stdout.write(f"\r{' ' * (len(ready) - 1)}{TEAL}◆{R}")
        sys.stdout.flush()
        _time.sleep(0.18)
        sys.stdout.write(f"\r{' ' * (len(ready) - 1)}{GRAY}◆{R}")
        sys.stdout.flush()
        _time.sleep(0.12)
    sys.stdout.write(f"\r{' ' * (len(ready) - 1)}{TEAL}◆{R}\n\n")
    sys.stdout.flush()
    _time.sleep(0.1)



def pick_session(conn, api_key):
    sessions = session_list(conn)
    if not sessions:
        _print_welcome_banner()
        model   = choose_model(api_key)
        agent   = choose_agent()
        session = session_create(conn, model, agent=agent)
        return session, model, []

    w = shutil.get_terminal_size((80, 20)).columns
    box_w = min(w - 2, 72)

    # ── Animate header wipe in ────────────────────────────────────────────────
    import time as _time
    header = f"  {TEAL}{BOLD}◈ Open CLI Codex{R}  {GRAY}sessions{R}"
    rule   = f"  {GRAY}{'─' * (box_w - 2)}{R}"
    print()
    # Header types in char by char
    _stripped = f"  ◈ Open CLI Codex  sessions"
    sys.stdout.write("  ")
    for i, ch in enumerate(f"◈ Open CLI Codex  sessions"):
        color = TEAL if i < 17 else GRAY
        sys.stdout.write(f"{color}{ch}{R}")
        sys.stdout.flush()
        _time.sleep(0.018)
    print()
    # Rule draws left→right
    sys.stdout.write("  ")
    for _ in range(box_w - 2):
        sys.stdout.write(f"{GRAY}─{R}")
        sys.stdout.flush()
        _time.sleep(0.004)
    print()

    # "new session" row fades in
    _time.sleep(0.05)
    print(f"  {GRAY} 0 {R}  {DIM}+ new session{R}")
    sys.stdout.write("  ")
    for _ in range(box_w - 2):
        sys.stdout.write(f"{GRAY}·{R}")
        sys.stdout.flush()
        _time.sleep(0.003)
    print()

    for i, s in enumerate(sessions, 1):
        dt    = datetime.fromtimestamp(s["updated_at"]).strftime("%m-%d %H:%M")
        tok   = s["token_input"] + s["token_output"]
        ag    = s.get("agent", AGENT_BUILD)
        ag_cl = BLUE if ag == AGENT_PLAN else GREEN
        short_model  = s['model'].split('/')[-1][:28]
        title_trunc  = s['title'][:40]
        prov_key     = s.get("provider") or ""
        prov_name    = PROVIDERS.get(prov_key, {}).get("name", prov_key) if prov_key else ""
        if prov_key and prov_key != _active_provider:
            prov_badge = f"  {YELLOW}⚠ {prov_name}{R}"
        elif prov_name:
            prov_badge = f"  {GRAY}{prov_name}{R}"
        else:
            prov_badge = ""
        # ── Cascade: brief dim placeholder then snap to full color ────────────
        _time.sleep(0.03)
        print(f"  {CYAN}{BOLD}{i:>2}{R}  {WHITE}{title_trunc}{R}  {ag_cl}[{ag}]{R}{prov_badge}")
        print(f"      {GRAY}{short_model}  ·  {dt}  ·  {tok:,} tok  ·  {s['directory']}{R}")

    # Bottom rule draws in
    sys.stdout.write("  ")
    for _ in range(box_w - 2):
        sys.stdout.write(f"{GRAY}─{R}")
        sys.stdout.flush()
        _time.sleep(0.004)
    print()
    print()

    while True:
        try:
            raw = input(f"  {TEAL}❯{R} ").strip()
            if not raw:
                continue
            n = int(raw)
            if n == 0:
                model   = choose_model(api_key)
                title   = input(f"  {DIM}Session name (Enter = auto): {R}").strip()
                agent   = choose_agent()
                session = session_create(conn, model, title, agent=agent)
                return session, model, []
            elif 1 <= n <= len(sessions):
                s    = sessions[n-1]
                msgs = messages_load(conn, s["id"])

                # ── Provider mismatch check ───────────────────────────────────
                saved_provider = s.get("provider") or ""
                if saved_provider and saved_provider != _active_provider:
                    saved_name   = PROVIDERS.get(saved_provider, {}).get("name", saved_provider)
                    current_name = PROVIDERS.get(_active_provider, {}).get("name", _active_provider)
                    print(f"\n  {YELLOW}⚠{R}  Session này dùng {BOLD}{saved_name}{R}"
                          f"  {DIM}({s['model'].split('/')[-1]}){R}")
                    print(f"  {DIM}Provider hiện tại: {R}{WHITE}{current_name}{R}")
                    print(f"  {DIM}Model cũ không tương thích — cần chọn model mới.{R}\n")
                    new_model = choose_model(api_key)
                    # Cập nhật model + provider mới vào session
                    session_update(conn, s["id"], model=new_model, provider=_active_provider)
                    s["model"]    = new_model
                    s["provider"] = _active_provider
                    print(f"  {GREEN}✓{R} {DIM}Resumed{R} {WHITE}{s['title']}{R}"
                          f"  {DIM}→ {new_model.split('/')[-1]}  ({len(msgs)} messages){R}\n")
                    return s, new_model, msgs

                # Session cũ chưa có provider → backfill provider hiện tại
                if not saved_provider:
                    session_update(conn, s["id"], provider=_active_provider)

                print(f"  {GREEN}✓{R} {DIM}Resumed{R} {WHITE}{s['title']}{R} {DIM}— {len(msgs)} messages{R}\n")
                return s, s["model"], msgs
        except KeyboardInterrupt:
            print(f"\n  {DIM}Bye.{R}"); sys.exit(0)
        except ValueError:
            print(f"  {RED}Nhập số hợp lệ (0–{len(sessions)}).{R}")
            continue

def choose_agent():
    print(f"\n  {GRAY}agent mode{R}")
    print(f"  {CYAN}1{R}  {GREEN}build{R}   {DIM}full access — write, edit, bash{R}")
    print(f"  {CYAN}2{R}  {BLUE}plan{R}    {DIM}read-only — safe analysis{R}")
    try:
        n = input(f"  {TEAL}❯{R} {DIM}[1]{R} ").strip()
        return AGENT_PLAN if n == "2" else AGENT_BUILD
    except (EOFError, KeyboardInterrupt):
        return AGENT_BUILD

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

HELP = f"""
{TEAL}{BOLD}◈ Open CLI Codex{R}  {GRAY}built-in commands{R}

{GRAY}Sessions & Navigation{R}
  {CYAN}/sessions{R}            switch / create session
  {CYAN}/session{R}             current session info
  {CYAN}/title <name>{R}        rename session
  {CYAN}/delete [id]{R}         delete session
  {CYAN}/deleteall{R}           delete ALL sessions
  {CYAN}/cd <path>{R}           change directory

{GRAY}Model & Agent{R}
  {CYAN}/model{R}               change model
  {CYAN}/agent{R}               switch agent mode  {DIM}(build / plan){R}
  {CYAN}/sequential{R}          step-by-step mode  {DIM}(safer, more tokens){R}
  {CYAN}/batch{R}               batched tool calls {DIM}(default, faster){R}
  {CYAN}/mode{R}                thinking on/off  {DIM}(if model supports it){R}
  {CYAN}/thinking{R}            Upstage reasoning_effort {DIM}(none / medium / high){R}

{GRAY}Context & Memory{R}
  {CYAN}/tokens{R}              token usage + cost
  {CYAN}/compact{R}             compact context manually
  {CYAN}/clear{R}               clear chat history
  {CYAN}/todos{R}               view todo list
  {CYAN}/cache [debug|off|clear]{R}  file cache status
  {CYAN}/checkpoint [label]{R}  save/list progress checkpoints

{GRAY}Files & History{R}
  {CYAN}/undo{R}                undo last file change
  {CYAN}/redo{R}                redo undone change
  {CYAN}/diff{R}                show changed files this session
  {CYAN}/sandbox{R}             show sandbox project_dir
  {CYAN}/export{R}              export conversation to markdown

{GRAY}Git{R}
  {CYAN}/commit{R}              AI writes commit message from staged diff
  {CYAN}/review{R}              AI reviews changes this session

{GRAY}Config & Extensions{R}
  {CYAN}/perm <tool> <level>{R} set permission  {DIM}(allow / ask / deny){R}
  {CYAN}/perms{R}               view current permissions
  {CYAN}/skills{R}              list available skills
  {CYAN}/setkey{R}              change API key  {DIM}(Enter trống để xoá){R}
  {CYAN}/deletekey{R}           xoá API key đã lưu
  {CYAN}/addkey <key>{R}        thêm key vào pool  {DIM}(nhiều key/provider, tự xoay khi 429){R}
  {CYAN}/listkeys{R}            xem pool key + trạng thái cooldown
  {CYAN}/rmkey <n>{R}           xoá key khỏi pool theo số thứ tự
  {CYAN}/keystrategy <s>{R}     round_robin | fill_first
  {CYAN}/init{R}                analyze project, create AGENTS.md
  {CYAN}/rules{R}               view active AGENTS.md rules
  {CYAN}/commands{R}            list custom commands
  {CYAN}/mcp [list|add|remove|refresh]{R}  MCP servers  {DIM}(Command Code only){R}
  {CYAN}/web{R}                 mở web UI local  {DIM}(terminal bridge qua trình duyệt){R}
  {CYAN}/format{R}              đổi format API cho model hiện tại  {DIM}(openai/anthropic/openai_responses){R}
  {CYAN}/help{R}                this screen
  {DIM}exit / quit / q{R}       quit

{GRAY}Input tricks{R}
  {GRAY}\\{R}               end line with \\ → continue on next line
  {GRAY}\"\"\"{R}            block input mode
  {GRAY}@file.txt{R}       attach file inline  {DIM}(Tab to autocomplete){R}
  {GRAY}↑ ↓{R}             history navigation

{GRAY}Custom commands{R}  {DIM}.fw_data/commands/<name>.md{R}
  {DIM}frontmatter: description · agent · model · subtask{R}
  {DIM}variables:   $ARGUMENTS  $1 $2  !`shell`  @file{R}

{GRAY}AI tools{R}  {DIM}bash · read · write · edit · glob · grep{R}
           {DIM}webfetch · websearch · todowrite · todoread{R}
           {DIM}question · apply_patch · task · skill · lsp{R}

{GRAY}Rules{R}   {DIM}AGENTS.md (project) · .fw_data/AGENTS.md (local){R}
{GRAY}Data{R}    {DIM}{DATA_DIR}{R}
"""


def _expand_at_mentions(text: str) -> str:
    """
    Expand @filename mentions in user prompt.
    @path/to/file  →  inline file content block.
    Uses fuzzy glob if exact path not found.
    """
    def _at_path_allowed(p: Path) -> bool:
        try:
            return _check_sandbox_read(str(p)) is None
        except Exception:
            return False

    def _at_candidate_files(raw: str) -> list[Path]:
        p = Path(raw).expanduser()
        if p.exists() and p.is_file() and _at_path_allowed(p):
            return [p]
        try:
            matches = sorted(Path.cwd().rglob(f"*{raw}*"))
        except Exception:
            return []
        return [x for x in matches if x.is_file() and _at_path_allowed(x)]

    def _replace(m):
        raw = m.group(1)
        matches = _at_candidate_files(raw)
        if not matches:
            return m.group(0)  # keep as-is
        p = matches[0]
        try:
            body = p.read_text(errors="replace")
            rel  = p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p
            return f"\n<file path=\"{rel}\">\n{body}\n</file>\n"
        except Exception:
            return m.group(0)
    # Match @word, @path/to/file, @file.ext (no spaces)
    return re.sub(r"@([\w./\\-]+)", _replace, text)

def _at_file_complete(prefix: str) -> list[str]:
    """List files matching prefix for @-autocomplete hint."""
    try:
        matches = sorted(Path.cwd().rglob(f"*{prefix}*"))
    except Exception:
        return []
    out = []
    for m in matches:
        if not m.is_file():
            continue
        if _check_sandbox_read(str(m)) is not None:
            continue
        out.append(str(m.relative_to(Path.cwd())))
        if len(out) >= 8:
            break
    return out

def _multiline_input(prompt):
    """
    Nhập nhiều dòng:
      - Kết thúc dòng bằng '\\' rồi Enter → tiếp tục dòng mới
      - Hoặc dùng triple-quote: nhập '\"\"\"' → Enter nhiều dòng → '\"\"\"' để kết thúc
    """
    lines = []
    first = True
    while True:
        try:
            line = input(prompt if first else f"{DIM}... {R}")
            first = False
        except EOFError:
            # Pipe/stdin closed — return what we have or None
            return "\n".join(lines).strip() if lines else None
        except KeyboardInterrupt:
            return None

        # Triple-quote mode: """
        if not lines and line.strip() == '"""':
            print(f"{DIM}(nhập nhiều dòng, kết thúc bằng '\"\"\"'){R}")
            while True:
                try:
                    inner = input(f"{DIM}  │ {R}")
                except (EOFError, KeyboardInterrupt):
                    break
                if inner.strip() == '"""':
                    break
                lines.append(inner)
            return "\n".join(lines).strip() or None

        # Backslash continuation
        if line.endswith("\\"):
            lines.append(line[:-1])
        else:
            lines.append(line)
            break

    return "\n".join(lines).strip()

def main():
    # B2 FIX: thiếu global cho các biến này khiến các lần "reset" ở /sessions
    # và /perm bash ask (xem dưới) chỉ tạo biến local trong main(), không
    # đụng tới biến module-level thật mà tool_bash()/_check_permission() đọc.
    global _input_history, _tool_mode, _thinking_mode, _upstage_thinking_effort, _bash_allow_all
    _input_history = history_load()
    choose_provider()
    api_key = get_api_key()
    conn    = db_connect()

    _tool_mode = "batch"  # mặc định batch, user có thể gõ /sequential để đổi
    _thinking_mode = "on"  # tự bật; /mode chỉ là override request, không chặn việc bắt thinking
    _upstage_thinking_effort = None  # chỉ dùng cho custom provider upstage qua /thinking

    session, model, messages = pick_session(conn, api_key)
    sid    = session["id"]
    short  = model.split("/")[-1]
    agent  = session.get("agent", AGENT_BUILD)

    global _current_agent
    _current_agent = agent

    _todos_init(conn, sid)
    _sandbox_init(conn, sid, session.get("project_dir"))
    undo_state_load(conn, sid)

    # ── SessionState: nền tảng chung cho CLI và (tương lai) web ──────────────
    # agent_turn(state=state) sẽ emit Event thay vì print() trực tiếp;
    # render_cli/cli_ask_handler ở đây tái tạo lại đúng UX terminal cũ.
    # Không thay giá trị trả về hay hành vi nào của agent_turn — chỉ đổi
    # ĐƯỜNG XUẤT của output.
    state = SessionState(conn, sid, model, agent, api_key, messages)
    state.bus.subscribe(render_cli)
    state.bus.subscribe_ask(cli_ask_handler)
    register_cli_state(state)  # /web sau này nối trực tiếp vào state này

    ag_cl = BLUE if agent == AGENT_PLAN else GREEN
    tm_cl = YELLOW if _tool_mode == "sequential" else TEAL
    tm_label = "seq" if _tool_mode == "sequential" else "batch"
    rules_hint = f"  {GREEN}◆ rules{R}" if load_agents_md() else ""
    w = shutil.get_terminal_size((80, 20)).columns
    bar_w = min(w - 4, 72)

    import time as _t2
    print()

    # ── Top bar: ━ draws from center outward ─────────────────────────────────
    half = bar_w // 2
    sys.stdout.write("  ")
    parts_l, parts_r = [], []
    for i in range(half):
        parts_l.insert(0, f"{TEAL}━{R}")
        parts_r.append(f"{TEAL}━{R}")
        sys.stdout.write(f"\r  {''.join(parts_l)}{''.join(parts_r)}")
        sys.stdout.flush()
        _t2.sleep(0.005)
    print()

    # ── Title line types in ───────────────────────────────────────────────────
    title_text = f"◈ Open CLI Codex  [{sid[:8]}]  {session['title']}"
    sys.stdout.write("  ")
    for ch in title_text:
        if ch == "◈":
            sys.stdout.write(f"{TEAL}{BOLD}◈{R}")
        elif ch == "[":
            sys.stdout.write(f"{GRAY}[")
        elif ch == "]":
            sys.stdout.write(f"]{R}")
        else:
            sys.stdout.write(ch)
        sys.stdout.flush()
        _t2.sleep(0.012)
    print()

    # ── Meta line ────────────────────────────────────────────────────────────
    print(f"  {GRAY}{short}{R}  "
          f"{ag_cl}◆ {agent}{R}  "
          f"{tm_cl}◆ {tm_label}{R}  "
          f"{GRAY}{os.getcwd()}{R}"
          f"{rules_hint}")

    # ── Bottom rule draws left→right ─────────────────────────────────────────
    sys.stdout.write("  ")
    for _ in range(bar_w):
        sys.stdout.write(f"{GRAY}─{R}")
        sys.stdout.flush()
        _t2.sleep(0.003)
    print()
    print(f"  {DIM}Type /help for commands  ·  @file to attach  ·  \\ to continue line{R}\n")

    while True:
        # Context bar + session cost trước prompt -- KHÔNG in khi web đang
        # armed: bàn phím CLI đã bị khoá lúc này (chỉ có đúng 4 dòng thông
        # báo từ wait_web_mode() là cần thiết), in thêm bar mỗi vòng lặp gây
        # rác màn hình CLI trong lúc user không thao tác được gì ở đó.
        _web_armed = state is not None and state.web_bridge is not None and state.web_bridge.is_armed()
        if messages and not _web_armed:
            bar = _context_bar(messages, model)
            cost_s = _session_cost_str()
            print(f"  {bar}  {cost_s}")
        try:
            ag_col  = BLUE if agent == AGENT_PLAN else GREEN
            user_images = None
            user = get_next_input(
                state,
                f"{GRAY}{short}{R} {ag_col}{agent}{R} {TEAL}{BOLD}❯{R} "
            )
            # Ảnh (nếu có) đi kèm dòng input này -- CHỈ khác None khi input
            # tới từ WS handler /web (xem gate trong get_next_input_images).
            # Đọc NGAY sau get_next_input(), trước khi vòng lặp có thể gọi
            # lại lần nữa (last_images bị next_line() ghi đè ở lần sau).
            user_images = get_next_input_images(state)
        except EOFError:
            user = None
            _cancel_bg.set()
        except KeyboardInterrupt:
            # ── Nút ^C trên Web UI (lúc KHÔNG có turn nào đang chạy) ────────
            # Đây LUÔN là interrupt đến từ push_interrupt() của web (next_line()
            # raise KeyboardInterrupt khi có "interrupt" trong queue) -- Ctrl-C
            # bàn phím CLI thật không thể xảy ra ở đây vì bàn phím CLI đã bị
            # khoá hoàn toàn trong lúc armed.
            #
            # Theo yêu cầu: ^C lúc KHÔNG có gì đang chạy (idle, đứng ở dấu
            # nhắc) không được làm gì cả -- không disarm, không thoát về CLI,
            # không tắt CLI. Web vẫn giữ nguyên trạng thái armed, người dùng
            # tiếp tục chat bình thường. (^C lúc AI ĐANG trả lời đã được xử
            # lý riêng, đúng chỗ, trong _stream_response/call_api_stream --
            # xem WebInputBridge._stream_interrupt.)
            if state is not None and state.web_bridge is not None and state.web_bridge.is_armed():
                continue
            user = None
            _cancel_bg.set()
        if user is None:
            print(f"\n  {DIM}Goodbye.{R}\n"); break
        # BUG: trước đây "if not user: continue" bỏ qua MỌI input rỗng --
        # đúng cho CLI (Enter suông = bỏ qua). Nhưng trên /web, người dùng
        # có thể gửi CHỈ ẢNH không kèm chữ (value rỗng, chỉ có images) --
        # user_images vẫn có dữ liệu dù user là "". Nếu vẫn continue ở đây,
        # ảnh bị nuốt hoàn toàn: không emit turn_start, không lưu, không
        # gọi AI -- đúng hiện tượng "gửi ảnh mà im lặng" đã gặp. Chỉ
        # continue khi THỰC SỰ không có gì cả (không chữ VÀ không ảnh).
        if not user and not user_images:
            continue

        # BUG ĐÃ SỬA: bấm chọn lệnh từ gợi ý (autocomplete) trên Web UI
        # (applySlashChoice ở web_index.html) luôn chèn "cmd + dấu cách"
        # vào ô nhập, kể cả với lệnh không cần tham số (/listkeys,
        # /deletekey...). Nếu Enter ngay không gõ thêm gì, "user" nhận về
        # là "/listkeys " (có 1 dấu cách thừa ở cuối) -- mọi so sánh
        # "user.lower() == '/listkeys'" bên dưới đều SO SÁNH TUYỆT ĐỐI nên
        # không bao giờ khớp, lệnh rơi tọt xuống nhánh custom-command cuối
        # file mà không báo lỗi gì -- đúng hiện tượng "gõ qua gợi ý thì vô
        # dụng, gõ tay thì chạy" (gõ tay hiếm khi có dấu cách thừa ở cuối
        # nên không lộ bug). Chỉ strip khi dòng LÀ 1 lệnh slash hoặc
        # exit/quit/q -- KHÔNG strip nội dung chat thường gửi cho AI (có
        # thể là multiline/code block, dấu cách đầu/cuối ở đó có thể có ý
        # nghĩa, không tự tiện đụng vào).
        _first_word = user.split(None, 1)[0] if user.split(None, 1) else ""
        if _first_word.startswith("/") or _first_word.lower() in ("exit", "quit", "q"):
            user = user.strip()

        # ── Web UI: chỉ dùng để chat/thao tác code, KHÔNG dùng để chạy lệnh
        # slash hay thoát chương trình ────────────────────────────────────
        # Quyết định: mọi lệnh "/..." VÀ exit/quit/q đều bị chặn khi đang
        # armed (web đang bật) — Web UI chỉ để chat với AI, mọi thao tác
        # quản lý (session/model/mcp...) hoặc thoát chương trình bắt buộc
        # quay lại CLI thật. exit/quit/q đặc biệt nguy hiểm nếu không
        # chặn: gõ từ web sẽ break vòng lặp và tắt hẳn tiến trình CLI thật
        # (không phải chỉ đóng tab web).
        #
        # NGOẠI LỆ (whitelist) — 5 lệnh quản lý API key: đã xác nhận qua
        # đọc source từng dòng rằng cả 5 handler đều đi 100% qua
        # state.emit()/state.ask() (bus), KHÔNG còn print()/input() nào
        # chạy khi có state (nhánh input()/print() cũ chỉ còn là fallback
        # cho state is None, không xảy ra khi vào từ web). /addkey và
        # /setkey dùng state.ask(kind="text") -- UI ô nhập đã có sẵn ở
        # web_index.html (renderAsk, nhánh kind==="text"), không cần thêm
        # UI mới. Cho phép chạy qua web vì đây là nhu cầu thực tế (đổi/thêm
        # key ngay trong lúc đang chat, không muốn phải quay lại CLI thật).
        #
        # /model: TRƯỚC ĐÂY không nằm trong whitelist vì choose_model() là
        # UI raw-mode terminal (tự vẽ/xoá màn hình bằng ANSI cursor), không
        # thể render lên web. Giờ block /model đã tự rẽ nhánh: khi armed
        # gọi _web_choose_model() (picker riêng qua state.ask(kind=
        # "model_picker"), JS renderModelPicker() vẽ list/search/phân
        # trang) thay vì choose_model() -- xem 09_api_system.py và
        # 10_main.py, block "if user.lower() == '/model':". Nhánh CLI thật
        # (không armed) vẫn dùng choose_model() y hệt cũ, không đổi gì.
        # /mode: TRƯỚC ĐÂY thuộc nhóm "chưa migrate" (toàn print() trần,
        # không emit qua bus) -- đã sửa xong, toàn bộ output giờ đi qua
        # state.emit() khi có state (xem block "if _cmd_parts[0] ==
        # '/mode':"). Không có input()/UI raw-mode nào, logic nghiệp vụ
        # (_probe_thinking_support/_probe_thinking_disable) không đổi gì.
        # /format: mới thêm — cho phép chạy qua web vì handler
        # (_ask_change_format) chỉ dùng state.emit()/state.ask(kind=
        # "choice"/"text"), không có input()/print() trần hay raw-mode
        # terminal nào (đã xác nhận qua đọc source, giống lý do 5 lệnh
        # key + /model/mode được whitelist ở trên).
        # /codeweb: xem 13_codeweb.py — handler (codeweb_handle_command) chỉ
        # dùng state.emit()/state.bus.ask(), không input()/print() trần,
        # giống lý do các lệnh trên được whitelist. Lệnh này CHỈ có ý nghĩa
        # khi armed trong web (đổi agent + bật layout 2 cột cho chính phiên
        # web đang mở), nên bắt buộc phải nằm trong whitelist này.
        _WEB_ALLOWED_CMDS = ("/listkeys", "/rmkey", "/deletekey", "/addkey", "/setkey", "/model", "/mode", "/thinking", "/format", "/codeweb")
        _cmd0 = user.split(None, 1)[0].lower() if user.split(None, 1) else ""
        if (state is not None and state.web_bridge is not None
                and state.web_bridge.is_armed()
                and (_cmd0.startswith("/") or _cmd0 in ("exit", "quit", "q"))
                and _cmd0 not in _WEB_ALLOWED_CMDS):
            state.emit(EV_WARN, text=(
                "Lệnh / (và exit/quit) không dùng được qua Web UI — bấm Esc "
                "trên CLI để chạy lệnh, Web UI chỉ để chat/thao tác code.\n"
                "(Riêng /listkeys /rmkey /deletekey /addkey /setkey /model /mode /thinking /format "
                "/codeweb on|off dùng được.)\n"
            ))
            continue

        if user.lower() in ("exit","quit","q"):
            print(f"  {DIM}Goodbye.{R}\n"); break

        if user.lower() == "/help":
            if state is not None:
                state.emit(EV_INFO, text=HELP, raw=True)
            else:
                print(HELP)
            continue

        if user.lower() == "/web":
            # Web nối TRỰC TIẾP vào session CLI đang chạy (state) -- không
            # spawn tiến trình con, không mở session mới (đúng quyết định đã
            # chốt). Trình duyệt là 1 client của cùng state.bus; render_web
            # gửi JSON qua WebSocket khi có client nối vào /ws.
            if web_server_running():
                host, port = web_server_addr()
            else:
                # __file__ trong namespace chung được fw.py set = path thật
                # của chính fw.py (dùng để tìm web_index.html cạnh nó).
                _fw_path_real = globals().get("__file__") or sys.argv[0]
                host, port = start_web_server(_fw_path_real)
            # Khoá bàn phím CLI hiện tại, arm() web_bridge, chờ Esc/Ctrl-C để
            # lấy lại quyền. Server + kết nối WS vẫn chạy nền trong lúc này.
            wait_web_mode(state, host, port, color_fns={"GREEN": GREEN, "DIM": DIM, "R": R})
            continue

        if user.lower() == "/codeweb" or user.lower().startswith("/codeweb "):
            # Toàn bộ logic thật nằm ở 13_codeweb.py (file riêng, tách khỏi
            # /web gốc — xem module đó để biết chi tiết). Chỉ có ý nghĩa khi
            # đang armed qua web (đã được đảm bảo bởi whitelist phía trên +
            # bản thân handler tự kiểm tra lại state.web_bridge). Cú pháp:
            # "/codeweb on" | "/codeweb off" — handler tự báo lỗi nếu thiếu
            # hoặc sai arg, không đoán ý.
            #
            # BUG ĐÃ SỬA: trước đây chỉ gọi codeweb_handle_command(state, arg)
            # và bỏ qua giá trị trả về — handler chỉ set state.agent/
            # _current_agent, KHÔNG đụng biến `agent` CỤC BỘ của main() (dòng
            # ~550, ~1848 dùng chính biến này khi gọi agent_turn(...,
            # agent=agent, ...)). Hệ quả: bấm /codeweb on/off qua lại nhiều
            # lần chỉ đổi label hiển thị trên web (qua EV_SESSION_META) chứ
            # KHÔNG đổi system prompt thật gửi lên provider — turn kế tiếp
            # vẫn dùng agent cũ. Giống hệt bug đã từng gặp và sửa cho /agent
            # gốc (xem dòng ~997: agent = choose_agent(); state.agent = agent)
            # và cho custom-command override (xem comment "BUG ĐÃ SỬA" quanh
            # dòng ~1770). Sửa: handler trả về agent mới (hoặc None nếu lỗi
            # cú pháp/chưa armed), gán lại biến cục bộ + session_update để
            # bền qua resume session sau, đúng pattern /agent gốc.
            _cw_arg = user.split(None, 1)[1] if " " in user else ""
            _cw_new_agent = codeweb_handle_command(state, _cw_arg)
            if _cw_new_agent is not None:
                agent = _cw_new_agent
                session_update(conn, sid, agent=agent)
            continue

        if user.lower() == "/todos":
            todos = todos_load(conn, sid)
            if not todos:
                if state is not None: state.emit(EV_INFO, text=f"{DIM}(no todos){R}\n", raw=True)
                else: print(f"{DIM}(no todos){R}\n")
                continue
            lines = []
            for t in todos:
                icon = {"pending":"○","in_progress":"◉","completed":"✓"}.get(t["status"],"○")
                lines.append(f"  {icon} [{t['id']}] {t['content']} {DIM}({t['status']}){R}")
            out = "\n".join(lines) + "\n"
            if state is not None: state.emit(EV_INFO, text=out, raw=True)
            else: print(out)
            continue

        if user.lower() == "/tokens":
            r   = conn.execute("SELECT token_input,token_output FROM session WHERE id=?", (sid,)).fetchone()
            est = estimate_tokens(messages)
            bar = _context_bar(messages, model)
            out = (f"{DIM}  session: {r['token_input']:,}↑  {r['token_output']:,}↓\n"
                   f"  context now: ~{est:,} tokens estimated\n"
                   f"  {bar}\n"
                   f"  {_session_cost_str()}{R}")
            if state is not None: state.emit(EV_INFO, text=out, raw=True)
            else: print(out)
            continue

        if user.lower().startswith("/checkpoint"):
            label = user[len("/checkpoint"):].strip()
            if label:
                cid = checkpoint_save(conn, sid, label, messages)
                out = f"{GREEN}✓ checkpoint saved{R} {DIM}{cid} — {label[:80]}{R}\n"
                if state is not None: state.emit(EV_INFO, text=out, raw=True)
                else: print(out)
                continue
            cps = checkpoints_load(conn, sid)
            if not cps:
                out = f"{DIM}(no checkpoints){R}\n"
                if state is not None: state.emit(EV_INFO, text=out, raw=True)
                else: print(out)
                continue
            lines = [f"\n{BOLD}Checkpoints:{R}"]
            for cp in cps:
                ts = datetime.fromtimestamp(cp["created_at"]).strftime("%m-%d %H:%M")
                lines.append(f"  {TEAL}{cp['id']}{R}  {DIM}{ts}{R}  {cp['label']}  {GRAY}{cp['summary']}{R}")
            out = "\n".join(lines) + "\n"
            if state is not None: state.emit(EV_INFO, text=out, raw=True)
            else: print(out)
            continue

        if user.lower().startswith("/cache"):
            global _cache_debug
            parts = user.split()
            sub   = parts[1].lower() if len(parts) > 1 else "show"

            def _emit_cache(text):
                if state is not None: state.emit(EV_INFO, text=text, raw=True)
                else: print(text)

            if sub in ("debug", "on"):
                _cache_debug = True
                _emit_cache(f"{GREEN}✓ cache debug ON{R}\n"); continue
            if sub in ("off",):
                _cache_debug = False
                _emit_cache(f"{YELLOW}✓ cache debug OFF{R}\n"); continue
            if sub in ("clear",):
                _file_cache.clear()
                _emit_cache(f"{YELLOW}✓ cache cleared ({len(_file_cache)} entries){R}\n"); continue
            # default: show cache status
            if not _file_cache:
                _emit_cache(f"{DIM}  (cache empty){R}\n"); continue
            sorted_c = sorted(_file_cache.items(), key=lambda kv: kv[1]["access"], reverse=True)
            total_chars = sum(len(v["content"]) for v in _file_cache.values())
            lines = [f"\n{BOLD}File cache ({len(_file_cache)} files, ~{total_chars:,} chars):{R}",
                     f"{DIM}  debug={'ON' if _cache_debug else 'OFF'}  "
                     f"limit={CACHE_MAX_FILES} files / {CACHE_MAX_CHARS:,} chars{R}"]
            for abs_path, info in sorted_c:
                rel = abs_path
                try: rel = str(Path(abs_path).relative_to(Path.cwd()))
                except ValueError: pass
                age      = int(time.time() - info["access"])
                syms     = len(info["symbols"])
                h        = info.get("hash", "?")
                lines_n  = len(info["content"].splitlines())
                chars_n  = len(info["content"])
                # Hiện inject type: full / symbols / preview
                if chars_n <= 200:
                    inject_type = f"{GREEN}full{R}"
                elif syms:
                    inject_type = f"{CYAN}symbols({syms}){R}"
                else:
                    inject_type = f"{YELLOW}preview{R}"
                lines.append(f"  {DIM}{rel}{R}  "
                      f"{lines_n}L/{chars_n:,}c  "
                      f"[{inject_type}]  "
                      f"hash={h}  "
                      f"{DIM}access {age}s ago{R}")
            lines.append(f"\n{DIM}  /cache debug   — bật log [cache +/-/~]")
            lines.append(f"  /cache off     — tắt log")
            lines.append(f"  /cache clear   — xoá cache{R}\n")
            _emit_cache("\n".join(lines))
            continue

        if user.lower() == "/session":
            r   = conn.execute("SELECT * FROM session WHERE id=?", (sid,)).fetchone()
            dt  = datetime.fromtimestamp(r["updated_at"]).strftime("%Y-%m-%d %H:%M")
            ag  = r["agent"] if "agent" in r.keys() else AGENT_BUILD
            out = (f"{DIM}  [{r['id']}] {r['title']}\n"
                   f"  model:   {r['model']}\n"
                   f"  agent:   {ag}\n"
                   f"  dir:     {r['directory']}\n"
                   f"  updated: {dt}\n"
                   f"  tokens:  {r['token_input']:,}↑  {r['token_output']:,}↓\n"
                   f"  messages: {len(messages)}{R}\n")
            if state is not None: state.emit(EV_INFO, text=out, raw=True)
            else: print(out)
            continue

        if user.lower() == "/sessions":
            session, model, messages = pick_session(conn, api_key)
            sid    = session["id"]
            short  = model.split("/")[-1]
            agent  = session.get("agent", AGENT_BUILD)
            _current_agent = agent
            _todos_init(conn, sid)
            _sandbox_init(conn, sid, session.get("project_dir"))
            undo_state_load(conn, sid)
            # C8/C14/C26 FIX: reset session-scoped globals khi switch session
            # Không reset → allow-all vẫn on, file timestamps sai
            # B2 FIX: cần "global _bash_allow_all" ở đầu main() để dòng dưới
            # đụng đúng biến module-level (trước đây chỉ tạo local var,
            # reset không có tác dụng — xem khai báo global ở đầu hàm main()).
            # (Bug #1 fix: allowlist bash giờ tự check ở MỌI lệnh — không còn
            # cờ "_BASH_CONFIRMED" cần reset theo session nữa.)
            _bash_allow_all = False
            _file_read_time.clear()
            # Giữ web_bridge cũ (nếu web đang mở/armed) sang state mới, để
            # kết nối WS hiện có không bị "mồ côi" khi đổi session -- chỉ
            # đổi nội dung phiên (sid/model/messages...), không đổi ai đang
            # cầm quyền input.
            _old_web_bridge = state.web_bridge
            state = SessionState(conn, sid, model, agent, api_key, messages)
            state.web_bridge = _old_web_bridge
            state.bus.subscribe(render_cli)
            state.bus.subscribe_ask(cli_ask_handler)
            register_cli_state(state)  # /web phải trỏ vào state MỚI
            print(f"{GREEN}✓ [{sid}]{R}\n"); continue

        if user.lower() == "/model":
            # TÁCH 2 NHÁNH theo yêu cầu: Web UI dùng picker riêng (list +
            # search + phân trang qua JSON/WS, không phải raw-mode terminal
            # UI của choose_model() -- vốn tự vẽ/xoá màn hình bằng ANSI
            # cursor, không thể hiện lên web được). CLI thật (không armed)
            # giữ NGUYÊN choose_model() như cũ, không đổi hành vi gì.
            _web_armed_now = state.web_bridge is not None and state.web_bridge.is_armed()
            if _web_armed_now:
                new_model = _web_choose_model(state, api_key)
                if new_model is None:
                    # Huỷ (đóng picker không chọn gì) -- không đổi model hiện tại.
                    continue
                model = new_model
            else:
                model = choose_model(api_key)
            short = model.split("/")[-1]
            session_update(conn, sid, model=model)
            state.model = model
            # BUG ĐÃ SỬA: metaEl trên web chỉ được set 1 lần duy nhất lúc
            # session_init (kết nối lần đầu / đổi hẳn sang SessionState
            # khác qua /sessions) -- xem web_index.html case "session_init".
            # Đổi model qua /model chỉ set state.model = model trên CÙNG 1
            # object state, không tạo state mới -> web KHÔNG BAO GIỜ được
            # báo để cập nhật tên model trên header, dù backend đã đổi
            # đúng. Sửa: emit EV_SESSION_META (hằng số đã khai báo sẵn từ
            # trước với đúng mục đích "đổi session/model/agent" nhưng chưa
            # từng được dùng tới) ngay sau khi đổi state.model -- JS có case
            # riêng cập nhật lại metaEl mà không đụng gì khác trong log
            # (không xoá lịch sử chat như session_init đầy đủ sẽ làm).
            # BUG ĐÃ SỬA (cùng gốc với session_init ở 12_web.py): đổi model
            # qua /model giữa chừng cũng phải cho frontend biết NGAY model
            # mới này đã từng biết hỗ trợ ảnh hay chưa (thay vì luôn mở khoá
            # mù quáng qua maybeResetVisionBlock rồi đợi thử lại mới biết).
            state.emit(EV_SESSION_META, model=state.model, agent=state.agent,
                       vision_support=_vision_support_get(state.model))
            out = f"{GREEN}✓ {short}{R}\n"
            state.emit(EV_INFO, text=out, raw=True)
            continue

        if user.lower() == "/format":
            # Trigger TAY cho đúng logic vốn chỉ tự chạy khi gặp HTTP 404
            # sai-format (xem _ask_change_format trong 09_api_system.py) —
            # dùng LẠI nguyên hàm đó, không viết logic riêng. Không rẽ
            # nhánh CLI/web như /model: _ask_change_format() chỉ gọi
            # state.emit()/state.ask(kind="choice"/"text") — cả 2 kind này
            # đã chạy đúng trên CLI (cli_ask_handler) VÀ web (web_ask_handler
            # + renderAsk, xem web_index.html) từ trước (chính nhánh 404 đã
            # chứng minh điều này), không cần UI raw-mode riêng như
            # choose_model() nên không cần tách 2 hàm như /model.
            _ask_change_format(state, model)
            continue

        if user.lower() == "/agent":
            # TODO: /agent dính CÙNG BUG với /model (metaEl không cập nhật
            # khi đổi state.agent trên cùng 1 object state) -- CHƯA sửa ở
            # đây vì /agent chưa nằm trong whitelist web (vẫn dùng
            # choose_agent() raw-mode input, chưa có nhánh web riêng như
            # _web_choose_model), nên bug này chưa thể lộ ra qua web (lệnh
            # bị chặn từ trước khi chạm tới đây). Khi /agent được tách
            # nhánh web (giống /model), nhớ thêm state.emit(EV_SESSION_META,
            # model=state.model, agent=state.agent) y hệt /model ở trên.
            agent = choose_agent()
            _current_agent = agent
            session_update(conn, sid, agent=agent)
            state.agent = agent
            ag_cl = BLUE if agent == AGENT_PLAN else GREEN
            out = f"{ag_cl}✓ agent={agent}{R}\n"
            state.emit(EV_INFO, text=out, raw=True)
            continue

        if user.lower() == "/sequential":
            _tool_mode = "sequential"
            _system_static_cache.clear()  # rebuild vì _tool_mode ko còn trong static, nhưng giữ để safe
            out = (f"{YELLOW}✓ Sequential mode — từng bước, verify mỗi bước.\n"
                   f"{DIM}  Tốn token hơn nhưng an toàn hơn cho project lớn.\n"
                   f"  Gõ /batch để về mặc định.{R}\n")
            if state is not None: state.emit(EV_INFO, text=out, raw=True)
            else: print(out)
            continue

        if user.lower() == "/batch":
            _tool_mode = "batch"
            _system_static_cache.clear()  # rebuild vì _tool_mode ko còn trong static, nhưng giữ để safe
            out = f"{GREEN}✓ Batch mode — gộp tool calls, tiết kiệm token. {DIM}(mặc định){R}\n"
            if state is not None: state.emit(EV_INFO, text=out, raw=True)
            else: print(out)
            continue

        _cmd_parts = user.split(None, 1)
        if _cmd_parts and _cmd_parts[0].lower() == "/mode":
            arg = _cmd_parts[1].strip().lower() if len(_cmd_parts) > 1 else ""

            if _is_upstage_custom_provider():
                _mode_msg = (f"{YELLOW}⚠ Upstage không dùng /mode. Hãy dùng /thinking "
                             f"(none / medium / high).{R}\n")
                if state is not None:
                    state.emit(EV_INFO, text=_mode_msg, raw=True)
                else:
                    print(_mode_msg)
                continue

            def _mode_out(text):
                """In ra CLI hoặc emit qua bus tuỳ có state hay không -- pattern
                dùng chung khắp file, tách hàm nhỏ ở đây vì /mode có nhiều
                dòng print() rải rác hơn hẳn các lệnh khác."""
                if state is not None:
                    state.emit(EV_INFO, text=text, raw=True)
                else:
                    print(text)

            if not arg:
                # Gõ /mode trống → hiện trạng thái hiện tại + gợi ý cách dùng
                state_cl = GREEN if _thinking_mode == "on" else DIM
                lines = [f"{state_cl}Thinking mode: {_thinking_mode}{R}"]
                supported = _thinking_support_get(model)
                if supported is True:
                    lines.append(f"{DIM}  Model này đã xác nhận hỗ trợ thinking.{R}")
                elif supported is False:
                    lines.append(f"{DIM}  Model này đã thử và KHÔNG hỗ trợ thinking.{R}")
                else:
                    lines.append(f"{DIM}  Chưa rõ model này có hỗ trợ thinking không — "
                          f"gõ {CYAN}/mode on{R}{DIM} để thử.{R}")
                lines.append(f"{DIM}  Gõ {CYAN}/mode on{R}{DIM} hoặc {CYAN}/mode off{R}{DIM} để đổi.{R}\n")
                _mode_out("\n".join(lines))
                continue

            if arg in ("on", "off"):
                supported = _thinking_support_get(model)
                if supported is None:
                    _mode_out(f"{DIM}  Đang kiểm tra model này có hỗ trợ thinking không...{R}")
                    supported = _probe_thinking_support(model, api_key)
                    _thinking_support_set(model, supported)
                if not supported:
                    _mode_out(f"{YELLOW}⚠ Model/provider này không hỗ trợ thinking "
                          f"(không trả reasoning_content/thinking block).{R}\n"
                          f"{DIM}  Đã ghi nhớ, lần sau /mode sẽ báo ngay không cần thử lại.{R}\n")
                    continue
                _thinking_mode = arg
                _mode_lines = [f"{GREEN}✓ Thinking mode: {arg}{R}"]
                _fmt_kind_mode = _format_kind_for(model)
                if arg == "on" and (_fmt_kind_mode == "anthropic" or _active_provider == "aws_bedrock"):
                    _mode_lines.append(f"{DIM}  Lưu ý: nội dung thinking sẽ hiện ra màn hình (màu xám/dim, "
                          f"tag [thinking]). Signature được lưu/replay tự động để giữ thinking "
                          f"hoạt động cả ở các turn sau có tool_calls (tối ưu cache); nếu history "
                          f"cũ thiếu signature hợp lệ, thinking sẽ tự tắt riêng cho turn đó thay "
                          f"vì báo lỗi.{R}")
                elif arg == "on" and _fmt_kind_mode == "openai_responses":
                    # KHÁC Anthropic: đây là bản tóm tắt (reasoning summary)
                    # do model tự viết lại, KHÔNG phải chain-of-thought thật
                    # (OpenAI không expose raw reasoning tokens qua API) —
                    # và KHÔNG có cơ chế signature/encrypted_content replay
                    # nào được làm ở bản này (ngoài scope "/mode on/off"),
                    # nên không ghi nhầm là "lưu/replay tự động" như nhánh
                    # Anthropic — tránh hứa hẹn sai tính năng chưa tồn tại.
                    _mode_lines.append(f"{DIM}  Lưu ý: đây là bản TÓM TẮT reasoning (không phải "
                          f"chain-of-thought thật — OpenAI không lộ token suy luận gốc), hiện ra "
                          f"màn hình dạng [thinking]. Chưa hỗ trợ lưu/replay reasoning qua nhiều "
                          f"lượt có tool_calls (khác Anthropic) — mỗi turn tự suy luận lại từ đầu.{R}")
                if (arg == "off" and (_fmt_kind_mode in ("anthropic", "openai_responses")
                                       or _active_provider == "aws_bedrock")
                        and not _thinking_disable_already_probed(model)):
                    # Lần đầu tắt thinking cho cặp (provider, model) này —
                    # probe xem field "disabled" có thực sự tắt được hay
                    # provider custom chấp nhận nhưng bỏ qua (vd 1 số
                    # gateway Anthropic-format third-party). Best-effort,
                    # 1 request rất nhẹ, chỉ chạy 1 lần rồi đánh dấu đã probe.
                    if _mode_lines:
                        _mode_out("\n".join(_mode_lines))
                        _mode_lines = []
                    works = _probe_thinking_disable(model, api_key)
                    _thinking_disable_mark_probed(model)  # đánh dấu đã probe, dù kết quả gì
                    if not works:
                        _mode_out(f"{YELLOW}⚠ Provider này có vẻ KHÔNG tắt được thinking thật dù đã "
                              f"gửi 'disabled' — model có thể tự bật thinking ngầm phía server.{R}\n"
                              f"{DIM}  Đây là giới hạn của provider/gateway, không phải lỗi của "
                              f"app. Nếu cần tắt hẳn, kiểm tra docs riêng của provider.{R}")
                if _mode_lines:
                    _mode_out("\n".join(_mode_lines))
                continue

        if _cmd_parts and _cmd_parts[0].lower() == "/thinking":
            arg = _cmd_parts[1].strip().lower() if len(_cmd_parts) > 1 else ""

            def _thinking_out(text):
                if state is not None:
                    state.emit(EV_INFO, text=text, raw=True)
                else:
                    print(text)

            if not _is_upstage_custom_provider():
                _thinking_out(
                    f"{YELLOW}⚠ /thinking chỉ dùng cho custom provider 'upstage'.{R}\n"
                    f"{DIM}  Provider hiện tại: {_active_provider}. Dùng /model để đổi provider/model nếu cần.{R}\n"
                )
                continue

            if not arg:
                cur = _upstage_thinking_effort or "unset"
                _thinking_out(
                    f"{GREEN if _upstage_thinking_effort else DIM}Upstage reasoning_effort: {cur}{R}\n"
                    f"{DIM}  Gõ {CYAN}/thinking none{R}{DIM}, {CYAN}/thinking medium{R}{DIM}, "
                    f"hoặc {CYAN}/thinking high{R}{DIM}.{R}\n"
                )
                continue

            effort = _upstage_normalize_thinking_effort(arg)
            if effort is None:
                _thinking_out(
                    f"{YELLOW}⚠ Giá trị không hợp lệ: {arg}{R}\n"
                    f"{DIM}  Upstage hỗ trợ: none, medium, high.{R}\n"
                )
                continue

            _upstage_thinking_effort = effort
            _thinking_out(f"{GREEN}✓ Upstage reasoning_effort: {effort}{R}\n")
            continue

        if user.lower() == "/clear":
            conn.execute("DELETE FROM message WHERE session_id=?", (sid,))
            conn.commit(); messages.clear()
            _txt = f"{YELLOW}Đã xoá lịch sử.{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        # BUG FIX: "/deletekey" cũng khớp startswith("/delete") nên bị nhánh
        # này nuốt mất trước khi chạy tới đúng chỗ xử lý "/deletekey" ở dưới
        # (dòng ~1322) — gõ "/deletekey 1" bị hiểu nhầm thành "/delete 1"
        # (xoá session id=1), báo "Không tìm thấy session: 1" dù ý người
        # dùng là xoá key thứ 1 trong pool. Loại trừ tường minh ở đây.
        if user.lower().startswith("/delete") and not user.lower().startswith("/deletekey"):
            parts = user.split()
            cmd   = parts[0].lower()

            if cmd == "/deleteall":
                sessions_all = session_list(conn)
                print(f"{RED}Xoá TẤT CẢ {len(sessions_all)} session? Không thể hoàn tác.{R}")
                try:
                    confirm = input(f"{CYAN}Nhập 'yes' để xác nhận: {R}").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print(); continue
                if confirm == "yes":
                    for old in sessions_all:
                        _delete_session_project_dir(old)
                    conn.execute("DELETE FROM session")
                    conn.commit()
                    print(f"{RED}✓ Đã xoá tất cả session. Thoát...{R}")
                    break
                else:
                    print(f"{DIM}Huỷ.{R}\n"); continue

            # /delete hoặc /delete <id>
            target_id = parts[1] if len(parts) > 1 else sid
            target    = conn.execute("SELECT * FROM session WHERE id=?", (target_id,)).fetchone()
            if not target:
                print(f"{RED}Không tìm thấy session: {target_id}{R}\n"); continue
            print(f"  {DIM}[{target['id']}] {target['title']} · {target['model'].split('/')[-1]}{R}")
            try:
                confirm = input(f"{CYAN}Xoá session này? [y/N]: {R}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(); continue
            if confirm not in ("y", "yes"):
                print(f"{DIM}Huỷ.{R}\n"); continue
            _delete_session_project_dir(dict(target))
            conn.execute("DELETE FROM session WHERE id=?", (target_id,))
            conn.commit()
            print(f"{GREEN}✓ Đã xoá [{target_id}]{R}")
            if target_id == sid:
                print(f"{YELLOW}Session hiện tại đã xoá. Thoát...{R}")
                break
            print(); continue

        if user.lower() == "/compact":
            before = len(messages)
            messages = compact_messages(messages, model, api_key)
            state.messages = messages
            messages_replace_all(conn, sid, messages)
            print(f"{GREEN}✓ {before} → {len(messages)} messages{R}\n"); continue

        if user.lower() == "/undo":
            _txt = f"{YELLOW}{do_undo()}{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/redo":
            _txt = f"{GREEN}{do_redo()}{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/diff":
            snaps = snapshots_load(conn, sid)
            if not snaps:
                _txt = f"{DIM}(no file changes in this session){R}\n"
                if state: state.emit(EV_INFO, text=_txt, raw=True)
                else: print(_txt)
                continue
            seen = {}
            for s in snaps:
                seen[s["path"]] = s  # keep latest per path
            _lines = []
            for path, s in seen.items():
                before = (s["before"] or "").splitlines(keepends=True)
                after  = s["after"].splitlines(keepends=True)
                diff   = list(difflib.unified_diff(before, after,
                              fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
                if diff:
                    for line in diff[:60]:
                        cl = GREEN if line.startswith("+") else (RED if line.startswith("-") else DIM)
                        _lines.append(f"{cl}{line}{R}")
                    if len(diff) > 60: _lines.append(f"{DIM}  (+{len(diff)-60} more lines){R}")
            _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/sandbox":
            _lines = []
            if _project_dir:
                _lines.append(f"\n{BOLD}Project sandbox:{R}")
                _lines.append(f"  {GREEN}{_project_dir.resolve()}{R}")
                try:
                    files = list(_project_dir.rglob("*"))
                    fcount = sum(1 for f in files if f.is_file())
                    dcount = sum(1 for f in files if f.is_dir())
                    _lines.append(f"  {DIM}{fcount} file(s), {dcount} dir(s){R}")
                except Exception:
                    pass
            else:
                _lines.append(f"{DIM}  (sandbox chua khoi tao){R}")
            _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/export":
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            out  = DATA_DIR / f"export_{sid}_{ts}.md"
            lines = [f"# Session {sid}\n\n"]
            for m in messages:
                role = m["role"].upper()
                c    = m["content"]
                if isinstance(c, list):
                    c = " ".join(p.get("text","") for p in c if isinstance(p, dict))
                lines.append(f"**{role}**\n\n{c}\n\n---\n\n")
            out.write_text("".join(lines))
            _txt = f"{GREEN}✓ Exported → {out}{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/perms":
            merged = dict(DEFAULT_PERMS)
            if agent == AGENT_PLAN: merged.update(PLAN_PERMS)
            merged.update(_custom_perms)
            _lines = [f"\n{BOLD}Permissions (agent={agent}):{R}"]
            for t, p in sorted(merged.items()):
                cl = GREEN if p==PERM_ALLOW else (YELLOW if p==PERM_ASK else RED)
                _lines.append(f"  {cl}{p:6}{R}  {t}")
            _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower().startswith("/perm "):
            parts = user.split()
            if len(parts) == 3:
                _, tool_name, level = parts
                if level in (PERM_ALLOW, PERM_ASK, PERM_DENY):
                    _custom_perms[tool_name] = level
                    if tool_name == "bash" and level == PERM_ASK:
                        _bash_allow_all = False  # reset allow-all khi user set lại bash=ask
                        if state is not None: state.bash_allow_all = False
                    cl = GREEN if level==PERM_ALLOW else (YELLOW if level==PERM_ASK else RED)
                    _txt = f"{cl}✓ {tool_name} = {level}{R}\n"
                else:
                    _txt = f"{RED}Level phải là: allow / ask / deny{R}\n"
            else:
                _txt = f"{RED}Usage: /perm <tool> <allow|ask|deny>{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/setkey":
            cfg = load_config()
            ck  = _prov()["config_key"]
            cur = cfg.get(ck, "")
            _info_lines = []
            if cur:
                _info_lines.append(f"{DIM}  Key hiện tại [{_prov()['name']}]: {cur[:8]}...{cur[-4:]}{R}")
            _info_lines.append(f"  {DIM}(Enter trống để xoá){R}")
            if state is not None:
                state.emit(EV_INFO, text="\n".join(_info_lines), raw=True)
                new_key = state.ask(
                    prompt="API key mới:",
                    kind="text",
                    default="",
                ) or ""
                new_key = str(new_key).strip()
            else:
                print("\n".join(_info_lines))
                try:
                    new_key = input(f"{CYAN}API key mới: {R}").strip()
                except (EOFError, KeyboardInterrupt):
                    print(); continue
            # FIX (đồng bộ key): `cfg` load ở đầu block (dòng ~1292) có thể
            # đã CŨ tại đây — giữa lúc đó và lúc người dùng gõ xong key
            # (state.ask()/input() chờ vô thời hạn) thread nền (vd _auto_
            # rename_session) có thể đã load-sửa-save config.json cho field
            # khác (pool). Ghi thẳng bằng `cfg` cũ sẽ xoá mất thay đổi đó
            # (lost update) — đã verify bằng test thực nghiệm. Bọc _pool_lock
            # + load_config() LẠI ngay trước khi set/pop field rồi save.
            with _pool_lock:
                cfg = load_config()
                if new_key:
                    cfg[ck] = new_key
                    save_config(cfg)
                else:
                    cfg.pop(ck, None)
                    save_config(cfg)
            if new_key:
                api_key = new_key
                if state is not None: state.api_key = api_key
                _txt = f"{GREEN}✓ Đã lưu key mới.{R}\n"
            else:
                _txt = f"{YELLOW}✓ Đã xoá key đã lưu. Dùng env {_prov()['env_key']}.{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        # /deletekey <n>: dễ gõ nhầm với /rmkey <n> (2 lệnh khác nhau —
        # /deletekey xoá key đơn lưu qua /setkey, /rmkey xoá theo index
        # trong pool). Không tham số nào được /deletekey đọc, nên trước đây
        # gõ "/deletekey 1" chỉ khớp startswith("/delete") ở trên rồi thôi —
        # giờ báo rõ để không rơi tự do thành tin nhắn gửi lên AI.
        if user.lower().startswith("/deletekey ") and user.lower() != "/deletekey":
            _txt = (f"{YELLOW}\"/deletekey\" không nhận tham số (xoá key đơn đang lưu). "
                     f"Muốn xoá key theo số thứ tự trong pool → dùng {CYAN}/rmkey <số>{YELLOW} "
                     f"(xem số qua {CYAN}/listkeys{YELLOW}).{R}\n")
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/deletekey":
            # FIX (đồng bộ key): bọc _pool_lock quanh toàn bộ read-modify-
            # write — không chờ input giữa chừng như /setkey nên cửa sổ
            # race hẹp hơn, nhưng vẫn có thể trùng với thread nền đang ghi
            # pool đúng lúc lệnh này chạy. Cùng nguyên tắc, cùng lock.
            with _pool_lock:
                cfg = load_config()
                ck  = _prov()["config_key"]
                cur = cfg.get(ck, "")
                if cur:
                    cfg.pop(ck, None)
                    save_config(cfg)
            if cur:
                api_key = os.environ.get(_prov()["env_key"], "")
                if state is not None: state.api_key = api_key
                env_note = (f" Key env đang có sẵn."
                            if api_key else
                            f" {YELLOW}Chưa có key env — cần /setkey hoặc đặt env {_prov()['env_key']}.{R}")
                _txt = f"{GREEN}✓ Đã xoá key [{_prov()['name']}]. Sẽ dùng env {_prov()['env_key']}.{env_note}{R}\n"
            else:
                _txt = (f"{YELLOW}Không có key đã lưu cho [{_prov()['name']}]. "
                      f"Đang dùng env {_prov()['env_key']}.{R}\n")
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        # ── Key pool: nhiều key/provider, tự xoay khi 429 (xem 11_key_pool.py) ──
        if user.lower().startswith("/addkey"):
            parts = user.split(maxsplit=1)
            if len(parts) < 2:
                if state is not None:
                    new_key = state.ask(
                        prompt=f"API key thêm vào pool [{_prov()['name']}]:",
                        kind="text",
                        default="",
                    ) or ""
                    new_key = str(new_key).strip()
                else:
                    try:
                        new_key = input(f"{CYAN}API key thêm vào pool: {R}").strip()
                    except (EOFError, KeyboardInterrupt):
                        print(); continue
                if not new_key:
                    _txt = f"{RED}Đã huỷ — không có key nào được thêm.{R}\n"
                    if state: state.emit(EV_INFO, text=_txt, raw=True)
                    else: print(_txt)
                    continue
            else:
                new_key = parts[1].strip()
            n = pool_add_key(new_key)
            _txt = f"{GREEN}✓ Đã thêm key vào pool [{_prov()['name']}] — tổng {n} key.{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/listkeys":
            pool = pool_list()
            if not pool:
                _txt = (f"{YELLOW}Chưa có key nào trong pool [{_prov()['name']}]. "
                      f"Dùng /addkey <key> để thêm.{R}\n")
            else:
                _lines = [f"{DIM}Pool [{_prov()['name']}] — strategy: {_pool_strategy()}{R}"]
                for i, e in enumerate(pool, 1):
                    status = (f"{YELLOW}cooldown {e['cooldown_remaining']:.0f}s{R}"
                              if e["cooldown_remaining"] > 0 else f"{GREEN}sẵn sàng{R}")
                    _lines.append(f"  {WHITE}{i}{R}. {_pool_mask(e['key'])}  "
                          f"{DIM}fail={e['fail_count']}{R}  {status}")
                _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower().startswith("/rmkey"):
            parts = user.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip().isdigit():
                _txt = f"{RED}Usage: /rmkey <số thứ tự từ /listkeys>{R}\n"
                if state: state.emit(EV_INFO, text=_txt, raw=True)
                else: print(_txt)
                continue
            removed = pool_remove_key(int(parts[1].strip()))
            if removed:
                _txt = f"{GREEN}✓ Đã xoá key {_pool_mask(removed)} khỏi pool.{R}\n"
            else:
                _txt = f"{RED}Không có key ở vị trí đó.{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower().startswith("/keystrategy"):
            parts = user.split(maxsplit=1)
            if len(parts) < 2 or parts[1].strip() not in _KEY_POOL_STRATEGIES:
                _txt = f"{RED}Usage: /keystrategy round_robin|fill_first{R}\n"
                if state: state.emit(EV_INFO, text=_txt, raw=True)
                else: print(_txt)
                continue
            pool_set_strategy(parts[1].strip())
            _txt = f"{GREEN}✓ Strategy: {parts[1].strip()}{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/skills":
            found = []
            for sd in SKILLS_DIRS:
                if sd.exists():
                    for f in sd.rglob("*.md"):
                        found.append(str(f.relative_to(sd)))
            _lines = []
            if found:
                _lines.append(f"\n{BOLD}Skills:{R}")
                for f in found: _lines.append(f"  {DIM}{f}{R}")
            else:
                _lines.append(f"{DIM}Không có skills. Tạo file .md trong:{R}")
                for sd in SKILLS_DIRS: _lines.append(f"  {DIM}{sd}{R}")
            _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower().startswith("/cd "):
            target = user[4:].strip()
            try:
                os.chdir(target)
                _txt = f"{GREEN}✓ {os.getcwd()}{R}\n"
            except Exception as e:
                _txt = f"{RED}{e}{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower().startswith("/title "):
            title = user[7:].strip()
            session_update(conn, sid, title=title)
            _txt = f"{GREEN}✓ {title}{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/init":
            print(f"\n{BOLD}{CYAN}[init]{R} Đang phân tích project...{R}")
            # Scan project structure
            tree_lines = _dir_tree(Path.cwd(), max_depth=3)
            tree_str   = "\n".join(tree_lines[:80])
            # Check for existing AGENTS.md
            agents_path = Path.cwd() / "AGENTS.md"
            existing = ""
            if agents_path.exists():
                existing = f"\n\nExisting AGENTS.md:\n{agents_path.read_text()[:2000]}"
            # Detect common files
            hints = []
            for f in ["package.json","pyproject.toml","Cargo.toml","go.mod",
                      "Makefile","requirements.txt","setup.py","pom.xml"]:
                if (Path.cwd() / f).exists(): hints.append(f)
            hint_str = ", ".join(hints) if hints else "none detected"
            init_prompt = f"""Analyze this project and create or improve an AGENTS.md file.

Project directory: {Path.cwd()}
Detected config files: {hint_str}

Directory tree:
{tree_str}{existing}

Create a concise AGENTS.md that includes:
1. Project overview (1-2 sentences)
2. Build, test, lint commands
3. Key directory structure
4. Code conventions and patterns
5. Any important gotchas or setup steps

Write the AGENTS.md content directly. Be concise but complete."""
            print(f"{DIM}  Generating AGENTS.md...{R}")
            result = _call_simple(
                [{"role":"user","content":init_prompt}],
                model, api_key)
            agents_content = result.get("text","").strip()
            if agents_content:
                # Strip markdown fences if present
                if agents_content.startswith("```"):
                    agents_content = re.sub(r"^```[^\n]*\n", "", agents_content)
                    agents_content = re.sub(r"\n```\s*$", "", agents_content)
                agents_path.write_text(agents_content)
                _txt = (f"{GREEN}✓ Đã tạo {agents_path}{R}\n"
                        f"{DIM}{agents_content[:400]}{'...' if len(agents_content)>400 else ''}{R}\n")
            else:
                _txt = f"{RED}✗ Không tạo được AGENTS.md{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/rules":
            rules = load_agents_md()
            _lines = []
            if rules:
                _lines.append(f"\n{BOLD}Rules đang active:{R}")
                _lines.append(f"{DIM}{rules[:1500]}{'...' if len(rules)>1500 else ''}{R}")
            else:
                _lines.append(f"{DIM}Không tìm thấy AGENTS.md. Chạy /init để tạo.{R}")
            _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower() == "/commands":
            cmds = load_custom_commands()
            _lines = []
            if cmds:
                _lines.append(f"\n{BOLD}Custom commands:{R}")
                for name, c in sorted(cmds.items()):
                    _lines.append(f"  {YELLOW}/{name}{R}  {DIM}{c['description']}{R}")
                    _tail = ""
                    if c["agent"]: _tail += f"      agent={c['agent']}"
                    if c["model"]: _tail += f"  model={c['model'].split('/')[-1]}"
                    if _tail: _lines.append(_tail)
            else:
                _lines.append(f"{DIM}Không có custom commands. Tạo .opencode/commands/*.md{R}")
            _txt = "\n".join(_lines) + "\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        if user.lower().startswith("/mcp"):
            if not mcp_is_active():
                print(f"{YELLOW}  /mcp chỉ dùng khi provider = Command Code "
                      f"(hiện tại: {_prov()['name']}).{R}\n")
                continue
            parts = user.split(maxsplit=2)
            sub   = parts[1].lower() if len(parts) > 1 else ""
            servers = mcp_servers_load()

            if sub in ("", "list", "status"):
                if not servers:
                    print(f"{DIM}  Chưa có MCP server nào. Dùng:{R}")
                    print(f"  {CYAN}/mcp add <name> <url>{R}")
                    print(f"\n{DIM}  vd: /mcp add notion https://mcp.notion.com/mcp{R}\n")
                    continue
                print(f"\n{CYAN}{BOLD}MCP servers:{R}")
                with Spinner("Đang kết nối MCP"):
                    mcp_refresh_all(verbose=False)
                for name, srv in servers.items():
                    status = _MCP_STATUS.get(name, "?")
                    n      = len(_MCP_TOOL_CACHE.get(name, []))
                    if status == "connected":
                        badge = f"{GREEN}● connected{R}  {DIM}{n} tool(s){R}"
                    elif status == "unauthorized":
                        badge = f"{YELLOW}● cần xác thực (auth){R}"
                    elif status == "error":
                        badge = f"{RED}● lỗi kết nối{R}"
                    else:
                        badge = f"{GRAY}● chưa kết nối{R}"
                    en = "" if srv.get("enabled", True) else f"  {DIM}(disabled){R}"
                    print(f"  {WHITE}{name}{R}  {DIM}{srv['url']}{R}")
                    print(f"    {badge}{en}")
                    if status in ("error", "unauthorized") and _MCP_LAST_ERROR.get(name):
                        print(f"    {DIM}└ {_MCP_LAST_ERROR[name]}{R}")
                    if status == "connected" and n:
                        for t in _MCP_TOOL_CACHE[name][:6]:
                            print(f"    {DIM}- mcp__{name}__{t.get('name','')}{R}")
                        if n > 6:
                            print(f"    {DIM}  ... +{n-6} more{R}")
                print()
                continue

            if sub == "add":
                if len(parts) < 3:
                    print(f"{YELLOW}  cú pháp: /mcp add <name> <url> [header: Authorization=Bearer xxx]{R}\n")
                    continue
                rest = parts[2].split()
                if len(rest) < 2:
                    print(f"{YELLOW}  cú pháp: /mcp add <name> <url>{R}\n")
                    continue
                name, url = rest[0], rest[1]
                headers = {}
                for kv in rest[2:]:
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        headers[k] = v
                mcp_add_server(name, url, headers)
                print(f"{DIM}  [mcp] đang kết nối {name}...{R}", end="", flush=True)
                tools = mcp_fetch_tools(name, mcp_servers_load()[name], force=True)
                status = _MCP_STATUS.get(name, "error")
                if status == "connected":
                    print(f"\r{GREEN}✓ Đã thêm & kết nối {name} — {len(tools)} tool(s).{R}            \n")
                elif status == "unauthorized":
                    print(f"\r{YELLOW}⚠ Đã thêm {name} nhưng cần xác thực (401/403). "
                          f"Thêm header Authorization qua /mcp add lại.{R}            \n")
                else:
                    print(f"\r{RED}✗ Đã lưu {name} nhưng không kết nối được. Kiểm tra URL.{R}            \n")
                continue

            if sub == "remove":
                if len(parts) < 3:
                    print(f"{YELLOW}  cú pháp: /mcp remove <name>{R}\n")
                    continue
                name = parts[2].strip().split()[0]
                if name in servers:
                    mcp_remove_server(name)
                    print(f"{GREEN}✓ Đã xoá MCP server '{name}'.{R}\n")
                else:
                    print(f"{YELLOW}  Không tìm thấy server '{name}'.{R}\n")
                continue

            if sub in ("refresh", "reconnect"):
                with Spinner("Đang kết nối MCP"):
                    mcp_refresh_all(verbose=False)
                print(mcp_status_summary() + "\n")
                continue

            print(f"{YELLOW}  Lệnh /mcp con không hợp lệ. Dùng: list, add, remove, refresh{R}\n")
            continue

        # C4 FIX: /commit handler was dead code (after /mcp continue). Moved here.
        if user.lower() == "/commit":
            diff = ""
            try:
                r = subprocess.run(
                    ["git", "diff", "--staged"],
                    capture_output=True, text=True, timeout=10, cwd=os.getcwd()
                )
                diff = r.stdout.strip()
            except Exception as e:
                print(f"{RED}✗ Không lấy được diff: {e}{R}\n"); continue
            if not diff:
                print(f"{YELLOW}  Không có staged changes. Chạy 'git add' trước.{R}\n"); continue
            print(f"{DIM}  [/commit] Đang tạo commit message...{R}")
            diff_preview = diff[:6000]  # giới hạn để không tốn quá nhiều token
            result = _call_simple(
                [{"role": "user", "content":
                    "Viết commit message theo Conventional Commits (type: subject).\n"
                    "Ngắn gọn, tiếng Anh, dùng imperative mood.\n"
                    "Nếu cần, thêm body ngắn (≤3 dòng) sau 1 dòng trắng.\n"
                    "Chỉ trả lời commit message, không giải thích.\n\n"
                    f"```diff\n{diff_preview}\n```"}],
                model, api_key
            )
            msg = result.get("text", "").strip()
            if not msg:
                print(f"{RED}✗ Không tạo được commit message.{R}\n"); continue
            _txt = f"\n{GREEN}{BOLD}Commit message:{R}\n{msg}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            try:
                confirm = input(f"{CYAN}  Dùng message này? [y/N/e(dit)]: {R}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(); continue
            if confirm in ("y", "yes"):
                r2 = subprocess.run(
                    ["git", "commit", "-m", msg],
                    capture_output=True, text=True, cwd=os.getcwd()
                )
                if r2.returncode == 0:
                    print(f"{GREEN}✓ Committed.{R}")
                    print(f"{DIM}{r2.stdout.strip()}{R}")
                else:
                    print(f"{RED}✗ git commit failed:\n{r2.stderr.strip()}{R}")
            elif confirm in ("e", "edit"):
                try:
                    edited = input(f"{CYAN}  Sửa: {R}").strip()
                    if edited:
                        r2 = subprocess.run(
                            ["git", "commit", "-m", edited],
                            capture_output=True, text=True, cwd=os.getcwd()
                        )
                        if r2.returncode == 0:
                            print(f"{GREEN}✓ Committed.{R}")
                            print(f"{DIM}{r2.stdout.strip()}{R}")
                        else:
                            print(f"{RED}✗ {r2.stderr.strip()}{R}")
                except (EOFError, KeyboardInterrupt):
                    pass
            else:
                print(f"{DIM}  Huỷ.{R}")
            print(); continue

        if user.lower() == "/review":
            # Lấy diff của session: git diff HEAD (unstaged+staged) hoặc file snapshots
            diff = ""
            try:
                r = subprocess.run(
                    ["git", "diff", "HEAD"],
                    capture_output=True, text=True, timeout=10, cwd=os.getcwd()
                )
                diff = r.stdout.strip()
                if not diff:
                    # Fallback: staged only
                    r2 = subprocess.run(
                        ["git", "diff", "--staged"],
                        capture_output=True, text=True, timeout=10, cwd=os.getcwd()
                    )
                    diff = r2.stdout.strip()
            except Exception:
                pass
            # Fallback: dùng file snapshots từ session nếu không có git diff
            if not diff:
                snaps = snapshots_load(conn, sid)
                if snaps:
                    parts = []
                    for s in snaps[-10:]:  # giới hạn 10 file cuối
                        before = s.get("before") or ""
                        after  = s.get("after") or ""
                        path   = s.get("path", "?")
                        if before != after:
                            d = "".join(difflib.unified_diff(
                                before.splitlines(keepends=True),
                                after.splitlines(keepends=True),
                                fromfile=f"a/{path}", tofile=f"b/{path}", n=3
                            ))
                            if d: parts.append(d)
                    diff = "\n".join(parts)
            if not diff:
                print(f"{YELLOW}  Không có thay đổi để review.{R}\n"); continue
            print(f"{DIM}  [/review] Đang review...{R}")
            diff_preview = diff[:8000]
            review_prompt = (
                "Review code diff dưới đây. Trả lời bằng tiếng Việt.\n"
                "Tập trung vào:\n"
                "1. Bug tiềm ẩn hoặc lỗi logic\n"
                "2. Vấn đề bảo mật\n"
                "3. Performance\n"
                "4. Readability / code style\n"
                "5. Đề xuất cải thiện cụ thể (nếu có)\n\n"
                f"```diff\n{diff_preview}\n```"
            )
            review_msgs = [{"role": "user", "content": review_prompt}]
            with Spinner("Đang review"):
                result = _call_simple(review_msgs, model, api_key)
            review_text = result.get("text", "").strip()
            if review_text:
                _txt = f"\n{GREEN}{BOLD}Code Review:{R}\n{review_text}\n"
            else:
                _txt = f"{RED}✗ Không tạo được review.{R}\n"
            if state: state.emit(EV_INFO, text=_txt, raw=True)
            else: print(_txt)
            continue

        # Custom slash commands (from .opencode/commands/*.md)
        if user.startswith("/") and not user.startswith("// "):
            cmd_name = user[1:].split()[0].lower()
            cmd_args = user[len(cmd_name)+2:].strip()  # everything after "/name "
            cmds = load_custom_commands()
            if cmd_name in cmds:
                cmd = cmds[cmd_name]
                template = cmd["template"]
                # $ARGUMENTS / positional $1 $2 ...
                template = template.replace("$ARGUMENTS", cmd_args)
                arg_parts = cmd_args.split() if cmd_args else []
                for idx, part in enumerate(arg_parts, 1):
                    template = template.replace(f"${idx}", part)
                # !`shell` → giữ cú pháp nhưng KHÔNG thực thi (an toàn mặc định)
                # Trả về warning để user biết command đã bị vô hiệu hoá.
                def _shell_inject(m):
                    cmd = (m.group(1) or "").strip()
                    cmd = cmd[:200] + ("…" if len(cmd) > 200 else "")
                    return ("[shell disabled] '!`...`' is disabled by default for safety. "
                            "Run this manually if you trust it. cmd=" + cmd)
                template = re.sub(r"!`([^`]+)`", _shell_inject, template)
                # @file references
                template = _expand_at_mentions(template)
                # Override agent/model if specified
                run_agent = cmd.get("agent") or agent
                run_model = cmd.get("model") or model
                print(f"{DIM}  [/{cmd_name}] {cmd['description']}{R}")
                if cmd.get("subtask"):
                    # Run as subagent
                    result = tool_task(template, model=run_model, api_key=api_key, conn=conn, sid=sid, state=state)
                    print(f"\n{GREEN}{BOLD}AI:{R} {result}")
                    messages.append({"role":"user","content":f"[/{cmd_name}] {template}"})
                    messages.append({"role":"assistant","content":result})
                    message_save(conn, sid, "user", f"[/{cmd_name}] {template}")
                    message_save(conn, sid, "assistant", result)
                else:
                    messages.append({"role":"user","content":template})
                    message_save(conn, sid, "user", template)
                    try:
                        state.model = run_model
                        state.agent = run_agent
                        messages = agent_turn(messages, run_model, api_key, conn, sid, agent=run_agent, state=state)
                        state.messages = messages
                    except KeyboardInterrupt:
                        cid = checkpoint_save(conn, sid, "interrupted", messages,
                                              "User interrupted agent turn; saved messages are intact.")
                        if state is not None:
                            state.emit(EV_INTERRUPTED, checkpoint_id=cid)
                        else:
                            print(f"\n{YELLOW}  checkpoint {cid} saved after interrupt{R}")
                    finally:
                        # BUG ĐÃ SỬA: run_model/run_agent chỉ là override RIÊNG
                        # cho lượt custom-command này (frontmatter "model:"/
                        # "agent:" trong file .md, field tùy chọn — phần lớn
                        # command không set, khi đó run_model==model/
                        # run_agent==agent nên fix này không đổi gì quan sát
                        # được). Trước đây state.model/state.agent bị set = 
                        # run_model/run_agent ở trên nhưng KHÔNG BAO GIỜ được
                        # phục hồi lại model/agent gốc của session sau khi turn
                        # kết thúc (dù thành công hay bị Ctrl+C) — biến local
                        # model/agent (dùng cho agent_turn() ở nhánh chat bình
                        # thường, dòng ~1786) không bị ảnh hưởng nên request
                        # thật vẫn đúng, nhưng state.model/state.agent bị lệch
                        # vĩnh viễn. Hệ quả quan sát được: 12_web.py
                        # (_send_session_init, gọi khi mở tab web mới/reconnect)
                        # đọc st.model/st.agent để hiển thị lên UI + tra
                        # vision_support theo model — nếu mở web sau khi vừa
                        # chạy 1 custom command có model/agent riêng, web hiện
                        # SAI tên model/agent và tra vision_support sai model.
                        # Dùng finally (không phải đặt cuối try) để đảm bảo
                        # phục hồi đúng CẢ KHI KeyboardInterrupt xảy ra giữa
                        # agent_turn (nhánh except phía trên không có gì đọc
                        # lại state.model/agent nên phục hồi ở đây không phá
                        # logic checkpoint/emit đã chạy trước đó).
                        state.model = model
                        state.agent = agent
                # Cùng bug print() trần vô điều kiện đã sửa ở nhánh chat
                # bình thường phía dưới -- nhánh custom-command này cũng
                # chạy khi gõ qua web (dù phần lớn UI custom-command chưa
                # emit qua bus, xem comment đầu 12_web.py), nên vẫn áp
                # cùng guard để nhất quán, tránh dòng trắng dư lặp lại nếu
                # người dùng gọi custom command từ web.
                if state is None or not (getattr(state, "web_bridge", None) and state.web_bridge.is_armed()):
                    print()
                continue

        # Expand @file mentions before sending
        expanded = _expand_at_mentions(user)
        if expanded != user:
            # Show what was expanded
            files = re.findall(r"@([\w./\-]+)", user)
            print(f"{DIM}  [@] Đã nhúng: {', '.join(files)}{R}")
        # KHÔNG inject time vào user message — phá cache prefix của API
        # Time chỉ lưu DB, không gửi lên API
        # Đếm trước khi append — tránh off-by-one khi resume session cũ
        is_first_turn = len([m for m in messages if m.get("role") == "user"]) == 0
        if user_images:
            # Content dạng OpenAI multimodal — 3 adapter (OpenAI-compat gốc,
            # Anthropic, AWS Bedrock) tự dịch tiếp ở tầng dưới (xem
            # _convert_content_blocks_to_anthropic / _to_converse). Ảnh chỉ
            # sống trong RAM (biến messages) — KHÔNG lưu DB (xem message_save
            # ngay dưới, dùng "expanded" thuần text, không phải content_val
            # có ảnh). Turn sau, _strip_old_images() (09_api_system.py) sẽ
            # tự thay ảnh này bằng placeholder khi build lại payload gọi API.
            content_val = [{"type": "text", "text": expanded or "(đã gửi ảnh, không kèm chữ)"}] + [
                {"type": "image_url",
                 "image_url": {"url": f"data:{im['mime']};base64,{im['data']}"}}
                for im in user_images
            ]
            messages.append({"role": "user", "content": content_val})
            message_save(conn, sid, "user", expanded or "(đã gửi ảnh, không kèm chữ)")
        else:
            messages.append({"role":"user","content":expanded})
            message_save(conn, sid, "user", expanded)
        try:
            messages = agent_turn(messages, model, api_key, conn, sid, agent=agent, state=state)
            state.messages = messages
        except KeyboardInterrupt:
            cid = checkpoint_save(conn, sid, "interrupted", messages,
                                  "User interrupted agent turn; saved messages are intact.")
            if state is not None:
                state.emit(EV_INTERRUPTED, checkpoint_id=cid)
            else:
                print(f"\n{YELLOW}  checkpoint {cid} saved after interrupt{R}")
        # Auto-rename session sau turn đầu tiên (nếu vẫn là tên mặc định)
        if is_first_turn:
            _auto_rename_session(conn, sid, messages, model, api_key)
        # BUG ĐÃ SỬA: print() trần vô điều kiện ở đây -- chạy sau MỖI turn
        # chat bình thường (không phải slash-command), không phân biệt input
        # đến từ bàn phím CLI thật hay từ web (web_bridge armed). Đây là
        # nguồn chính của "mỗi lần chat qua web, CLI lại dư 1 dòng trắng":
        # mọi tin nhắn gửi từ web đều đi qua chính nhánh này ở cuối main
        # loop. Áp dụng cùng guard đã dùng cho các print() trần khác
        # (xem 09_api_system.py call_api_stream/_agent_turn_inner).
        if state is None or not (getattr(state, "web_bridge", None) and state.web_bridge.is_armed()):
            print()

if __name__ == "__main__":
    main()
