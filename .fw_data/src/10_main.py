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
        import concurrent.futures as _cf
        def _api_call():
            return _call_simple(
                [{"role": "user", "content":
                    f"Đặt tên ngắn (tối đa 5 từ tiếng Việt, không dấu chấm) "
                    f"cho cuộc hội thoại bắt đầu bằng:\n\n{first_user}\n\n"
                    f"Chỉ trả lời tên, không giải thích."}],
                model, api_key
            )
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
                fut = _ex.submit(_api_call)
                result = fut.result(timeout=15)  # timeout 15s — tránh zombie thread
            new_title = result.get("text", "").strip().strip('"').strip("'")
            # Sanity: không dài hơn 60 ký tự, không chứa newline
            new_title = new_title.splitlines()[0][:60].strip()
            if new_title:
                session_update(conn, sid, title=new_title)
        except Exception:
            pass  # silent fail — không quan trọng nếu rename lỗi

    threading.Thread(target=_do_rename, daemon=True).start()


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

def choose_tool_mode() -> str:
    """Hỏi user muốn model dùng ít hay nhiều API call."""
    print(f"\n  {GRAY}tool call mode{R}")
    print(f"  {CYAN}1{R}  {TEAL}batch{R}       {DIM}group tool calls — faster, cheaper{R}")
    print(f"  {CYAN}2{R}  {CYAN}sequential{R}  {DIM}step-by-step — safer, easier to debug{R}")
    try:
        n = input(f"  {TEAL}❯{R} {DIM}[1]{R} ").strip()
        if n == "2":
            return "sequential"
        return "batch"
    except (EOFError, KeyboardInterrupt):
        return "batch"

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
  {CYAN}/init{R}                analyze project, create AGENTS.md
  {CYAN}/rules{R}               view active AGENTS.md rules
  {CYAN}/commands{R}            list custom commands
  {CYAN}/mcp [list|add|remove|refresh]{R}  MCP servers  {DIM}(Command Code only){R}
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
    import fnmatch as _fnmatch
    def _replace(m):
        raw = m.group(1)
        # Try exact path first
        p = Path(raw).expanduser()
        if not p.exists():
            # Fuzzy: glob from cwd
            matches = sorted(Path.cwd().rglob(f"*{raw}*"))
            matches = [x for x in matches if x.is_file()]
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
    matches = sorted(Path.cwd().rglob(f"*{prefix}*"))
    return [str(m.relative_to(Path.cwd())) for m in matches if m.is_file()][:8]

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
    # B2 FIX: thiếu global cho 2 biến này khiến các lần "reset" ở /sessions
    # và /perm bash ask (xem dưới) chỉ tạo biến local trong main(), không
    # đụng tới biến module-level thật mà tool_bash()/_check_permission() đọc.
    global _input_history, _tool_mode, _BASH_CONFIRMED, _bash_allow_all
    _input_history = history_load()
    choose_provider()
    api_key = get_api_key()
    conn    = db_connect()

    _tool_mode = "batch"  # mặc định batch, user có thể gõ /sequential để đổi

    session, model, messages = pick_session(conn, api_key)
    sid    = session["id"]
    short  = model.split("/")[-1]
    agent  = session.get("agent", AGENT_BUILD)

    global _current_agent
    _current_agent = agent

    _todos_init(conn, sid)
    _sandbox_init(conn, sid, session.get("project_dir"))

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
        # Context bar + session cost trước prompt
        if messages:
            bar = _context_bar(messages, model)
            cost_s = _session_cost_str()
            print(f"  {bar}  {cost_s}")
        try:
            ag_col  = BLUE if agent == AGENT_PLAN else GREEN
            user = _multiline_input_with_hint(
                f"{GRAY}{short}{R} {ag_col}{agent}{R} {TEAL}{BOLD}❯{R} "
            )
        except (EOFError, KeyboardInterrupt):
            user = None
        if user is None:
            print(f"\n  {DIM}Goodbye.{R}\n"); break
        if not user: continue

        if user.lower() in ("exit","quit","q"):
            print(f"  {DIM}Goodbye.{R}\n"); break

        if user.lower() == "/help":         print(HELP); continue

        if user.lower() == "/todos":
            todos = todos_load(conn, sid)
            if not todos: print(f"{DIM}(no todos){R}\n"); continue
            for t in todos:
                icon = {"pending":"○","in_progress":"◉","completed":"✓"}.get(t["status"],"○")
                print(f"  {icon} [{t['id']}] {t['content']} {DIM}({t['status']}){R}")
            print(); continue

        if user.lower() == "/tokens":
            r   = conn.execute("SELECT token_input,token_output FROM session WHERE id=?", (sid,)).fetchone()
            est = estimate_tokens(messages)
            bar = _context_bar(messages, model)
            print(f"{DIM}  session: {r['token_input']:,}↑  {r['token_output']:,}↓")
            print(f"  context now: ~{est:,} tokens estimated")
            print(f"  {bar}")
            print(f"  {_session_cost_str()}{R}"); continue

        if user.lower().startswith("/checkpoint"):
            label = user[len("/checkpoint"):].strip()
            if label:
                cid = checkpoint_save(conn, sid, label, messages)
                print(f"{GREEN}✓ checkpoint saved{R} {DIM}{cid} — {label[:80]}{R}\n")
                continue
            cps = checkpoints_load(conn, sid)
            if not cps:
                print(f"{DIM}(no checkpoints){R}\n"); continue
            print(f"\n{BOLD}Checkpoints:{R}")
            for cp in cps:
                ts = datetime.fromtimestamp(cp["created_at"]).strftime("%m-%d %H:%M")
                print(f"  {TEAL}{cp['id']}{R}  {DIM}{ts}{R}  {cp['label']}  {GRAY}{cp['summary']}{R}")
            print(); continue

        if user.lower().startswith("/cache"):
            global _cache_debug
            parts = user.split()
            sub   = parts[1].lower() if len(parts) > 1 else "show"
            if sub in ("debug", "on"):
                _cache_debug = True
                print(f"{GREEN}✓ cache debug ON{R}\n"); continue
            if sub in ("off",):
                _cache_debug = False
                print(f"{YELLOW}✓ cache debug OFF{R}\n"); continue
            if sub in ("clear",):
                _file_cache.clear()
                print(f"{YELLOW}✓ cache cleared ({len(_file_cache)} entries){R}\n"); continue
            # default: show cache status
            if not _file_cache:
                print(f"{DIM}  (cache empty){R}\n"); continue
            sorted_c = sorted(_file_cache.items(), key=lambda kv: kv[1]["access"], reverse=True)
            total_chars = sum(len(v["content"]) for v in _file_cache.values())
            print(f"\n{BOLD}File cache ({len(_file_cache)} files, ~{total_chars:,} chars):{R}")
            print(f"{DIM}  debug={'ON' if _cache_debug else 'OFF'}  "
                  f"limit={CACHE_MAX_FILES} files / {CACHE_MAX_CHARS:,} chars{R}")
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
                print(f"  {DIM}{rel}{R}  "
                      f"{lines_n}L/{chars_n:,}c  "
                      f"[{inject_type}]  "
                      f"hash={h}  "
                      f"{DIM}access {age}s ago{R}")
            print(f"\n{DIM}  /cache debug   — bật log [cache +/-/~]")
            print(f"  /cache off     — tắt log")
            print(f"  /cache clear   — xoá cache{R}\n")
            continue

        if user.lower() == "/session":
            r   = conn.execute("SELECT * FROM session WHERE id=?", (sid,)).fetchone()
            dt  = datetime.fromtimestamp(r["updated_at"]).strftime("%Y-%m-%d %H:%M")
            ag  = r["agent"] if "agent" in r.keys() else AGENT_BUILD
            print(f"{DIM}  [{r['id']}] {r['title']}")
            print(f"  model:   {r['model']}")
            print(f"  agent:   {ag}")
            print(f"  dir:     {r['directory']}")
            print(f"  updated: {dt}")
            print(f"  tokens:  {r['token_input']:,}↑  {r['token_output']:,}↓")
            print(f"  messages: {len(messages)}{R}\n"); continue

        if user.lower() == "/sessions":
            session, model, messages = pick_session(conn, api_key)
            sid    = session["id"]
            short  = model.split("/")[-1]
            agent  = session.get("agent", AGENT_BUILD)
            _current_agent = agent
            _todos_init(conn, sid)
            _sandbox_init(conn, sid, session.get("project_dir"))
            _undo_stack.clear(); _redo_stack.clear()
            # C8/C14/C26 FIX: reset session-scoped globals khi switch session
            # Không reset → bash không cần confirm, allow-all vẫn on, file timestamps sai
            # B2 FIX: cần "global _BASH_CONFIRMED, _bash_allow_all" ở đầu main() để
            # 2 dòng dưới đụng đúng biến module-level (trước đây chỉ tạo local var,
            # reset không có tác dụng — xem khai báo global ở đầu hàm main()).
            _BASH_CONFIRMED = False
            _bash_allow_all = False
            _file_read_time.clear()
            print(f"{GREEN}✓ [{sid}]{R}\n"); continue

        if user.lower() == "/model":
            model = choose_model(api_key)
            short = model.split("/")[-1]
            session_update(conn, sid, model=model)
            print(f"{GREEN}✓ {short}{R}\n"); continue

        if user.lower() == "/agent":
            agent = choose_agent()
            _current_agent = agent
            session_update(conn, sid, agent=agent)
            ag_cl = BLUE if agent == AGENT_PLAN else GREEN
            print(f"{ag_cl}✓ agent={agent}{R}\n"); continue

        if user.lower() == "/sequential":
            _tool_mode = "sequential"
            _system_static_cache.clear()  # rebuild vì _tool_mode ko còn trong static, nhưng giữ để safe
            print(f"{YELLOW}✓ Sequential mode — từng bước, verify mỗi bước.")
            print(f"{DIM}  Tốn token hơn nhưng an toàn hơn cho project lớn.{R}")
            print(f"{DIM}  Gõ /batch để về mặc định.{R}\n"); continue

        if user.lower() == "/batch":
            _tool_mode = "batch"
            _system_static_cache.clear()  # rebuild vì _tool_mode ko còn trong static, nhưng giữ để safe
            print(f"{GREEN}✓ Batch mode — gộp tool calls, tiết kiệm token. {DIM}(mặc định){R}\n"); continue

        if user.lower() == "/clear":
            conn.execute("DELETE FROM message WHERE session_id=?", (sid,))
            conn.commit(); messages.clear()
            print(f"{YELLOW}Đã xoá lịch sử.{R}\n"); continue

        if user.lower().startswith("/delete"):
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
            messages_replace_all(conn, sid, messages)
            print(f"{GREEN}✓ {before} → {len(messages)} messages{R}\n"); continue

        if user.lower() == "/undo":
            print(f"{YELLOW}{do_undo()}{R}\n"); continue

        if user.lower() == "/redo":
            print(f"{GREEN}{do_redo()}{R}\n"); continue

        if user.lower() == "/diff":
            snaps = snapshots_load(conn, sid)
            if not snaps:
                print(f"{DIM}(no file changes in this session){R}\n"); continue
            seen = {}
            for s in snaps:
                seen[s["path"]] = s  # keep latest per path
            for path, s in seen.items():
                before = (s["before"] or "").splitlines(keepends=True)
                after  = s["after"].splitlines(keepends=True)
                diff   = list(difflib.unified_diff(before, after,
                              fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
                if diff:
                    for line in diff[:60]:
                        cl = GREEN if line.startswith("+") else (RED if line.startswith("-") else DIM)
                        print(f"{cl}{line}{R}")
                    if len(diff) > 60: print(f"{DIM}  (+{len(diff)-60} more lines){R}")
            print(); continue

        if user.lower() == "/sandbox":
            if _project_dir:
                print(f"\n{BOLD}Project sandbox:{R}")
                print(f"  {GREEN}{_project_dir.resolve()}{R}")
                try:
                    files = list(_project_dir.rglob("*"))
                    fcount = sum(1 for f in files if f.is_file())
                    dcount = sum(1 for f in files if f.is_dir())
                    print(f"  {DIM}{fcount} file(s), {dcount} dir(s){R}")
                except Exception:
                    pass
            else:
                print(f"{DIM}  (sandbox chua khoi tao){R}")
            print(); continue

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
            print(f"{GREEN}✓ Exported → {out}{R}\n"); continue

        if user.lower() == "/perms":
            merged = dict(DEFAULT_PERMS)
            if agent == AGENT_PLAN: merged.update(PLAN_PERMS)
            merged.update(_custom_perms)
            print(f"\n{BOLD}Permissions (agent={agent}):{R}")
            for t, p in sorted(merged.items()):
                cl = GREEN if p==PERM_ALLOW else (YELLOW if p==PERM_ASK else RED)
                print(f"  {cl}{p:6}{R}  {t}")
            print(); continue

        if user.lower().startswith("/perm "):
            parts = user.split()
            if len(parts) == 3:
                _, tool_name, level = parts
                if level in (PERM_ALLOW, PERM_ASK, PERM_DENY):
                    _custom_perms[tool_name] = level
                    if tool_name == "bash" and level == PERM_ASK:
                        _bash_allow_all = False  # reset allow-all khi user set lại bash=ask
                    cl = GREEN if level==PERM_ALLOW else (YELLOW if level==PERM_ASK else RED)
                    print(f"{cl}✓ {tool_name} = {level}{R}\n")
                else:
                    print(f"{RED}Level phải là: allow / ask / deny{R}\n")
            else:
                print(f"{RED}Usage: /perm <tool> <allow|ask|deny>{R}\n")
            continue

        if user.lower() == "/setkey":
            cfg = load_config()
            ck  = _prov()["config_key"]
            cur = cfg.get(ck, "")
            if cur:
                print(f"{DIM}  Key hiện tại [{_prov()['name']}]: {cur[:8]}...{cur[-4:]}{R}")
            print(f"  {DIM}(Enter trống để xoá){R}")
            try:
                new_key = input(f"{CYAN}API key mới: {R}").strip()
            except (EOFError, KeyboardInterrupt):
                print(); continue
            if new_key:
                cfg[ck] = new_key
                api_key = new_key
                save_config(cfg)
                print(f"{GREEN}✓ Đã lưu key mới.{R}\n")
            else:
                cfg.pop(ck, None)
                save_config(cfg)
                print(f"{YELLOW}✓ Đã xoá key đã lưu. Dùng env {_prov()['env_key']}.{R}\n")
            continue

        if user.lower() == "/deletekey":
            cfg = load_config()
            ck  = _prov()["config_key"]
            cur = cfg.get(ck, "")
            if cur:
                cfg.pop(ck, None)
                save_config(cfg)
                api_key = os.environ.get(_prov()["env_key"], "")
                env_note = (f" Key env đang có sẵn."
                            if api_key else
                            f" {YELLOW}Chưa có key env — cần /setkey hoặc đặt env {_prov()['env_key']}.{R}")
                print(f"{GREEN}✓ Đã xoá key [{_prov()['name']}]. Sẽ dùng env {_prov()['env_key']}.{env_note}{R}\n")
            else:
                print(f"{YELLOW}Không có key đã lưu cho [{_prov()['name']}]. "
                      f"Đang dùng env {_prov()['env_key']}.{R}\n")
            continue

        if user.lower() == "/skills":
            found = []
            for sd in SKILLS_DIRS:
                if sd.exists():
                    for f in sd.rglob("*.md"):
                        found.append(str(f.relative_to(sd)))
            if found:
                print(f"\n{BOLD}Skills:{R}")
                for f in found: print(f"  {DIM}{f}{R}")
            else:
                print(f"{DIM}Không có skills. Tạo file .md trong:{R}")
                for sd in SKILLS_DIRS: print(f"  {DIM}{sd}{R}")
            print(); continue

        if user.lower().startswith("/cd "):
            target = user[4:].strip()
            try:   os.chdir(target); print(f"{GREEN}✓ {os.getcwd()}{R}\n")
            except Exception as e: print(f"{RED}{e}{R}\n")
            continue

        if user.lower().startswith("/title "):
            title = user[7:].strip()
            session_update(conn, sid, title=title)
            print(f"{GREEN}✓ {title}{R}\n"); continue

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
                print(f"{GREEN}✓ Đã tạo {agents_path}{R}")
                print(f"{DIM}{agents_content[:400]}{'...' if len(agents_content)>400 else ''}{R}")
            else:
                print(f"{RED}✗ Không tạo được AGENTS.md{R}")
            print(); continue

        if user.lower() == "/rules":
            rules = load_agents_md()
            if rules:
                print(f"\n{BOLD}Rules đang active:{R}")
                print(f"{DIM}{rules[:1500]}{'...' if len(rules)>1500 else ''}{R}")
            else:
                print(f"{DIM}Không tìm thấy AGENTS.md. Chạy /init để tạo.{R}")
            print(); continue

        if user.lower() == "/commands":
            cmds = load_custom_commands()
            if cmds:
                print(f"\n{BOLD}Custom commands:{R}")
                for name, c in sorted(cmds.items()):
                    print(f"  {YELLOW}/{name}{R}  {DIM}{c['description']}{R}")
                    if c["agent"]: print(f"      agent={c['agent']}", end="")
                    if c["model"]: print(f"  model={c['model'].split('/')[-1]}", end="")
                    if c["agent"] or c["model"]: print()
            else:
                print(f"{DIM}Không có custom commands. Tạo .opencode/commands/*.md{R}")
            print(); continue

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
            print(f"\n{GREEN}{BOLD}Commit message:{R}\n{msg}\n")
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
                print(f"\n{GREEN}{BOLD}Code Review:{R}\n{review_text}\n")
            else:
                print(f"{RED}✗ Không tạo được review.{R}\n")
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
                    result = tool_task(template, model=run_model, api_key=api_key, conn=conn, sid=sid)
                    print(f"\n{GREEN}{BOLD}AI:{R} {result}")
                    messages.append({"role":"user","content":f"[/{cmd_name}] {template}"})
                    messages.append({"role":"assistant","content":result})
                    message_save(conn, sid, "user", f"[/{cmd_name}] {template}")
                    message_save(conn, sid, "assistant", result)
                else:
                    messages.append({"role":"user","content":template})
                    message_save(conn, sid, "user", template)
                    try:
                        messages = agent_turn(messages, run_model, api_key, conn, sid, agent=run_agent)
                    except KeyboardInterrupt:
                        cid = checkpoint_save(conn, sid, "interrupted", messages,
                                              "User interrupted agent turn; saved messages are intact.")
                        print(f"\n{YELLOW}  checkpoint {cid} saved after interrupt{R}")
                print(); continue

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
        messages.append({"role":"user","content":expanded})
        message_save(conn, sid, "user", expanded)
        try:
            messages = agent_turn(messages, model, api_key, conn, sid, agent=agent)
        except KeyboardInterrupt:
            cid = checkpoint_save(conn, sid, "interrupted", messages,
                                  "User interrupted agent turn; saved messages are intact.")
            print(f"\n{YELLOW}  checkpoint {cid} saved after interrupt{R}")
        # Auto-rename session sau turn đầu tiên (nếu vẫn là tên mặc định)
        if is_first_turn:
            _auto_rename_session(conn, sid, messages, model, api_key)
        print()

if __name__ == "__main__":
    main()
