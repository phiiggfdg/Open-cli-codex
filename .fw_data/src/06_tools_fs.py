def get_active_tools() -> list:
    """Full tool schema is kept stable to preserve prompt-cache reuse."""
    return TOOLS

# ════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ════════════════════════════════════════════════════════════════════════════


# Các pattern bash nguy hiểm có thể escape sandbox
_BASH_DENY_PATTERNS = [
    r"\bsudo\b",
    r"\bsu\s",
    r"\bchroot\b",
    r"\bmount\b",
    r"\bdd\s",
    r"\brm\s+-rf\s+/",     # rm -rf /
    r"\brm\s+-rf\s+~",     # rm -rf ~ (home dir trên Termux)
    r"\brm\s+-rf\s+\$HOME", # rm -rf $HOME
    r"\bchmod\s+[0-7]*\s+/",
    r"\bchown\b.*\s+/",
    r"^\s*sed(?:\s|$)",     # file mutation must use edit/multiedit/apply_patch
]
_BASH_DENY_RE = re.compile("|".join(_BASH_DENY_PATTERNS))


# ── Bash safety gates ───────────────────────────────────────────────────────
# Bash is arbitrary code execution, not an OS sandbox. Permission and command
# validation are independent: /perm bash allow skips the prompt, never this gate.
# One tool call may contain exactly one command. Rejecting shell composition
# keeps the allowlist meaningful instead of merely checking the first command.
_BASH_ALLOWED_COMMANDS = {
    # Project/status inspection
    "pwd", "ls", "rg", "grep", "wc", "file", "stat", "tree", "which",
    "basename", "dirname", "date", "uname", "whoami", "echo", "printf",
    # Version control, tests, runtimes, package/build tools
    "git", "pytest", "python", "python3", "node", "npm", "pnpm", "yarn",
    "make", "pip", "pip3", "ruff", "mypy", "eslint", "tsc",
}
_BASH_SERVE_COMMANDS = {"python", "python3", "node", "npm", "pnpm", "yarn"}

# No chaining, pipes, redirects, subshells, command substitution, variable
# expansion, or multiline shell. Quoted/escaped punctuation remains ordinary
# argv text, which keeps regex patterns such as 'foo|bar$' usable with rg/grep.
def _bash_has_unquoted_shell_control(command: str) -> bool:
    quote = None
    escaped = False
    for char in command:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char in ";&|<>`$()!\n\r":
            return True
    return False


def _bash_command_name(token: str) -> str:
    name = Path(token).name.lower()
    if re.fullmatch(r"python3(?:\.\d+)?", name):
        return "python3"
    if re.fullmatch(r"pip3(?:\.\d+)?", name):
        return "pip3"
    return name


def _bash_path_is_inside_project(raw: str) -> bool:
    """Reject explicit paths that resolve outside project_dir.

    This is a path guard, not a sandbox: an allowed Python/Node script still has
    the permissions of this process and must itself be trusted.
    """
    if _project_dir is None:
        return not raw.startswith(("/", "~", ".."))
    value = raw.split("=", 1)[-1] if "=" in raw else raw
    if "://" in value or not value:
        return True
    looks_like_path = value.startswith(("/", "~", ".")) or "/" in value
    if not looks_like_path:
        return True
    try:
        proj = _project_dir.resolve()
        expanded = Path(value).expanduser()
        resolved = expanded.resolve() if expanded.is_absolute() else (proj / expanded).resolve()
        resolved.relative_to(proj)
        return True
    except Exception:
        return False


def _validate_bash_command(command: str, for_serve: bool = False):
    """Return (allowed, reason, argv) for one non-composed shell command."""
    command = (command or "").strip()
    if not command:
        return False, "Lệnh trống.", []
    if _bash_has_unquoted_shell_control(command):
        return False, (
            "Không hỗ trợ nối lệnh, pipe, redirect, subshell, biến shell hoặc "
            "lệnh nhiều dòng. Mỗi lần gọi bash chỉ chạy một command."
        ), []
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as e:
        return False, f"Cú pháp quote không hợp lệ: {e}", []
    if not argv:
        return False, "Lệnh trống.", []

    name = _bash_command_name(argv[0])
    allowed = _BASH_SERVE_COMMANDS if for_serve else _BASH_ALLOWED_COMMANDS
    if "/" in argv[0] or "\\" in argv[0]:
        return False, "Phải gọi command bằng tên trong PATH, không gọi executable qua path.", argv
    if name not in allowed:
        return False, f"Command '{name}' không nằm trong allowlist.", argv

    # BUG FIX: trước đây dùng "-c" in argv[1:] (flat scan toàn bộ args) nên
    # "python3 script.py -c val" và "python3 -m pytest -c cfg.ini" bị block
    # sai — "-c" là arg của script/module, không phải của interpreter.
    # Fix: chỉ scan flags TRƯỚC tên script (first non-flag arg), bỏ qua
    # "-m <module>" (là interpreter-level flag, không phải script name).
    if name in ("python", "python3"):
        i = 1
        while i < len(argv):
            a = argv[i]
            if a == "-c":
                return False, "python -c bị chặn; hãy viết file .py trong project rồi chạy file đó.", argv
            if a == "-m" and i + 1 < len(argv):
                i += 2  # bỏ qua "-m <module>", tiếp tục check flag sau module
                continue
            if not a.startswith("-"):
                break   # đã tới tên script — mọi arg sau đây thuộc về script
            i += 1
    if name == "node":
        _node_eval_flags = {"-e", "--eval", "-p", "--print"}
        for a in argv[1:]:
            if a in _node_eval_flags:
                return False, "node eval/print inline bị chặn; hãy chạy file .js trong project.", argv
            if not a.startswith("-"):
                break   # đã tới tên script


    if name == "git":
        lower = [a.lower() for a in argv[1:]]
        if "push" in lower:
            return False, "git push là thay đổi remote và không được chạy qua Bash tool.", argv
        if "clean" in lower or ("reset" in lower and "--hard" in lower):
            return False, "git clean và git reset --hard bị chặn vì khó khôi phục.", argv
    if name in ("npm", "pnpm", "yarn") and "publish" in [a.lower() for a in argv[1:]]:
        return False, "Publish package là thay đổi remote và bị chặn.", argv

    lower = [a.lower() for a in argv[1:]]
    is_pip_install = name in ("pip", "pip3") and "install" in lower
    is_python_pip_install = (
        name in ("python", "python3") and lower[:2] == ["-m", "pip"]
        and "install" in lower
    )
    if (is_pip_install or is_python_pip_install) and "--break-system-packages" not in argv[1:]:
        return False, "Termux yêu cầu pip install kèm --break-system-packages.", argv

    if name == "ls" and any(a == "--recursive" or (a.startswith("-") and "R" in a[1:]) for a in argv[1:]):
        return False, "ls recursive bị chặn; dùng glob với pattern hẹp.", argv

    for arg in argv[1:]:
        if arg.startswith("-C") and len(arg) > 2 and not _bash_path_is_inside_project(arg[2:]):
            return False, f"Path nằm ngoài project bị chặn: {arg[2:]}", argv
        if arg.startswith("-") and "=" not in arg:
            continue
        if not _bash_path_is_inside_project(arg):
            return False, f"Path nằm ngoài project bị chặn: {arg}", argv

    if for_serve:
        valid_server = (
            (name in ("python", "python3") and lower[:2] == ["-m", "http.server"])
            or (name == "node" and bool(argv[1:]) and not argv[1].startswith("-"))
            or (name == "npm" and lower[:1] in (["start"], ["run"]))
            or (name in ("pnpm", "yarn") and bool(lower)
                and lower[0] in ("run", "start", "dev", "serve", "preview"))
        )
        if not valid_server:
            return False, (
                "serve: chỉ cho phép python -m http.server, node <file>, npm run/start, "
                "hoặc pnpm/yarn run|start|dev|serve|preview."
            ), argv
    return True, "", argv

# ── Nhánh riêng: "serve:" — chạy 1 process SỐNG MÃI (preview dev server) ────
# Lý do cần tách hẳn khỏi logic bash thường (không chung code path, không
# đụng allowlist/deny/timeout cũ ở dưới): subprocess.run(...) mặc định CHỜ
# process kết thúc. Với 1 lệnh cố ý chạy mãi mãi (http.server, node listen,
# npm run dev...), nó KHÔNG BAO GIỜ tự thoát -- tool_bash cũ luôn timeout sau
# N giây. Nhánh serve dùng Popen + process group riêng để server có thể
# sống nền và được dọn trọn group khi thay thế, không tích luỹ process giữ cổng.
#
# Cú pháp: "serve: <lệnh thật>", ví dụ "serve: python3 -m http.server 8080".
# Không dùng cú pháp này -> rơi xuống nhánh bash thường bên dưới, KHÔNG đổi
# hành vi hiện có cho bất kỳ lệnh nào khác (git/pytest/npm/make/...).
#
# Hành vi:
#   - Luôn chạy NỀN (Popen, không chờ), trả về ngay lập tức -- không timeout,
#     vì đây là hành vi MONG MUỐN (server phải sống mãi), không phải lỗi.
#   - start_new_session=True (tương đương setsid) -- process con nằm trong
#     process group RIÊNG, nên khi cần kill, os.killpg() dọn được CẢ shell
#     lẫn process thật bên trong nó (khác hẳn lỗi zombie ở tool_bash thường).
#   - Gọi "serve: <lệnh y hệt lệnh cũ>" lần nữa -> tự kill server cũ (cùng
#     lệnh, so khớp chuỗi lệnh y hệt) rồi start lại, KHÔNG báo lỗi "đã chạy
#     rồi" dù trùng -- đúng yêu cầu: luôn thay thế êm, không báo lỗi.
#   - Gọi "serve: <lệnh KHÁC>" -> vẫn kill lệnh serve TRƯỚC ĐÓ (chỉ giữ tối đa
#     1 server serve sống tại 1 thời điểm cho mỗi session/project) rồi start
#     lệnh mới -- tránh tích luỹ nhiều zombie như bug đã xác nhận ở tool_bash.
#   - Không đụng chạm allowlist/deny/timeout của nhánh bash thường bên dưới.
_SERVE_PREFIX_RE = re.compile(r"^\s*serve\s*:\s*", re.IGNORECASE)
_serve_procs: dict[str, dict] = {}  # project_dir_str -> {"proc": Popen, "cmd": str, "port_hint": str}

def _serve_cleanup_all():
    for key in list(_serve_procs):
        _serve_kill_existing(key)

atexit.register(_serve_cleanup_all)

def _atomic_write_text(path: Path, content: str) -> None:
    """Replace a text file atomically, preserving UTF-8 and avoiding partial writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing_mode = path.stat().st_mode & 0o7777
    except OSError:
        existing_mode = None
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        if existing_mode is not None:
            os.fchmod(fd, existing_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        try: Path(tmp_name).unlink(missing_ok=True)
        except Exception: pass

# Nhận diện cổng CHỈ cho `python(3) -m http.server [PORT]` -- đây là lệnh serve
# duy nhất mà ta CHẮC CHẮN biết quy tắc định tuyến của nó (phục vụ file tĩnh
# đúng theo cây thư mục, không có routing/rewrite riêng như dev server
# framework). Với các lệnh khác (npm run dev, node server.js, vite...) không
# thể đoán chắc port lẫn file entry thật (có thể có SPA fallback, proxy, hay
# port tự chọn ngẫu nhiên nếu bận) -- cố đoán bừa sẽ đưa ra gợi ý SAI còn tệ
# hơn không gợi ý, nên các lệnh đó không kích hoạt auto-detect bên dưới.
_HTTP_SERVER_RE = re.compile(
    r"^\s*python3?\s+-m\s+http\.server(?:\s+(\d+))?\s*$", re.IGNORECASE
)

def _serve_detect_entry_file(run_cwd: str) -> tuple[bool, str | None]:
    """Trả về (index_ok, suggested_file):
      - index_ok=True  -> đã có "index.html" ở root, http.server tự phục vụ
        đúng, KHÔNG cần cảnh báo/gợi ý gì thêm (suggested_file luôn None).
      - index_ok=False, suggested_file=<tên file> -> không có index.html,
        nhưng có ĐÚNG 1 file *.html khác ở root -- an toàn để gợi ý thẳng.
      - index_ok=False, suggested_file=None -> mơ hồ (0 hoặc >1 file .html,
        không phải index.html) -- KHÔNG đoán, gọi _serve_list_html_files()
        riêng để lấy danh sách đầy đủ cho việc báo cáo.
    Đây là fallback khi agent QUÊN nêu path cụ thể trong câu trả lời cho
    user -- lý do bug 404 thực tế đã xảy ra: server chạy đúng thư mục
    project, nhưng agent chỉ báo "http://localhost:8080" (root, không có
    file), trong khi `python -m http.server` không tự phục vụ index.html
    nếu KHÔNG có file tên đúng "index.html" ở root -- nó liệt kê thư mục
    (hoặc 404 nếu directory listing bị tắt), không tự đoán sang file .html
    khác có sẵn.
    """
    try:
        root = Path(run_cwd)
        if (root / "index.html").is_file():
            return True, None
        html_files = sorted(
            p.name for p in root.iterdir()
            if p.is_file() and p.suffix.lower() == ".html"
        )
    except Exception:
        return True, None  # best-effort -- lỗi quét thư mục không được làm hỏng serve;
        # coi như "ok" để KHÔNG in cảnh báo sai khi thực ra không quét được.
    if len(html_files) == 1:
        return False, html_files[0]
    return False, None  # 0 hoặc >1 file -- mơ hồ, không đoán bừa

def _serve_list_html_files(run_cwd: str) -> list[str]:
    """Liệt kê TẤT CẢ file .html ở root run_cwd -- dùng khi không thể auto-pick
    1 file duy nhất (0 hoặc >1 file), để tool trả thông tin đầy đủ cho agent
    tự chọn thay vì im lặng/đoán sai."""
    try:
        root = Path(run_cwd)
        return sorted(
            p.name for p in root.iterdir()
            if p.is_file() and p.suffix.lower() == ".html"
        )
    except Exception:
        return []

def _serve_log(run_cwd: str, message: str) -> None:
    """No-op: đã tắt ghi file log debug .cw_serve_log.txt (từng dùng để debug
    trên máy thật khi không gắn được pdb). Giữ nguyên hàm + chữ ký để mọi lời
    gọi _serve_log(...) rải rác trong code không cần sửa lại -- chỉ đổi hành
    vi bên trong thành không làm gì, không tạo file rác trong project user."""
    pass

def _serve_key() -> str:
    """1 server 'serve' sống tối đa mỗi project -- dùng project_dir làm key
    (không phải sid) để agent nào cũng thấy/kill đúng process của project đó,
    nhất quán với cách project_dir đã là ranh giới cho mọi tool file khác."""
    if _project_dir is not None:
        return str(_project_dir.resolve())
    return os.getcwd()

def _serve_kill_existing(key: str) -> str | None:
    """Kill server 'serve' cũ của project này (nếu có), trả về lệnh cũ đã bị
    kill (để log/thông báo), hoặc None nếu chưa có gì chạy. Im lặng nếu
    process đã tự chết từ trước (poll() != None) -- không coi là lỗi."""
    entry = _serve_procs.pop(key, None)
    if not entry:
        return None
    proc = entry["proc"]
    old_cmd = entry["cmd"]
    if proc.poll() is None:  # vẫn đang chạy thật
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # cứng đầu -> kill hẳn
        except ProcessLookupError:
            pass  # đã chết giữa lúc kiểm tra -- không sao
        except Exception as write_error:
            pass  # dọn best-effort, không để lỗi kill làm hỏng luồng start-mới
    return old_cmd

# Bắt số port từ CUỐI lệnh serve (vd "python3 -m http.server 8080",
# "node server.js 3000", "vite --port 5173") -- chỉ cần số đứng riêng lẻ
# (ranh giới \b) để không bắt nhầm số bên trong path/tên file. Không bắt
# được -> bỏ qua bước check port (an toàn, không đoán bừa), rơi về hành vi
# cũ y hệt trước khi có fix này.
def _serve_find_port(inner_command: str) -> int | None:
    """Parse only documented/explicit port positions; never guess from digits."""
    try:
        argv = shlex.split(inner_command)
    except ValueError:
        return None
    name = _bash_command_name(argv[0]) if argv else ""
    candidate = None
    if name in ("python", "python3") and argv[1:3] == ["-m", "http.server"]:
        if len(argv) > 3 and argv[3].isdigit():
            candidate = argv[3]
        else:
            candidate = "8000"
    else:
        for i, arg in enumerate(argv[1:], 1):
            if arg in ("--port", "-p") and i + 1 < len(argv):
                candidate = argv[i + 1]
                break
            if arg.startswith("--port="):
                candidate = arg.split("=", 1)[1]
                break
    if candidate and candidate.isdigit() and 1 <= int(candidate) <= 65535:
        return int(candidate)
    return None

def _serve_port_available(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()

def _serve_kill_port_owner(run_cwd: str, port: int) -> str | None:
    """Refuse to signal processes that were not started by this CLI."""
    _serve_log(run_cwd,
               f"Port {port} is occupied by an untracked process; refusing to kill it.")
    return None

def tool_bash_serve(inner_command: str, argv: list[str]) -> str:
    """Nhánh 'serve:' của tool_bash -- xem comment khối phía trên. Tách hàm
    riêng để code path hoàn toàn độc lập, dễ đọc, không lẫn vào nhánh bash
    thường (không share biến/state nào ngoài _project_dir đọc-only)."""
    inner_command = inner_command.strip()
    if not inner_command:
        return "[serve] Thiếu lệnh sau 'serve:'. Cú pháp: serve: <lệnh chạy server>."
    key = _serve_key()
    guessed_port = _serve_find_port(inner_command)
    if (guessed_port is not None and not _serve_port_available(guessed_port)
            and key not in _serve_procs):
        return (f"[serve] Port {guessed_port} đang do tiến trình khác sử dụng. "
                "Không tự ý kill tiến trình ngoài; hãy chọn port khác hoặc tự dừng nó.")
    old_cmd = _serve_kill_existing(key)
    if old_cmd:
        time.sleep(0.15)  # đệm nhỏ: os.killpg gửi SIGTERM cho cả process group,
        # nhưng process con trong group có thể cần thêm chút thời gian để tự thoát.
        # Không có đệm này, bước check port ngay sau đây có
        # thể vẫn thấy port "bận" bởi chính con của server VỪA kill (race), rồi
        # báo nhầm nó là "process lạ" trong message trả về -- vô hại về chức
        # năng (vẫn kill đúng, port vẫn được giải phóng) nhưng gây hiểu lầm khi
        # đọc log/thông báo.
    run_cwd = str(_project_dir.resolve()) if _project_dir is not None else os.getcwd()
    _serve_log(run_cwd, f"=== serve: gọi mới === lệnh='{inner_command}' run_cwd='{run_cwd}' "
                        f"old_cmd={old_cmd!r} _project_dir={_project_dir!r}")
    # Log liệt kê TOÀN BỘ file ở run_cwd NGAY TRƯỚC KHI Popen chạy -- đây là
    # bằng chứng quan trọng nhất để debug 404: nếu index.html/file mong đợi
    # KHÔNG xuất hiện trong log này, nghĩa là file chưa từng nằm ở run_cwd
    # tại đúng thời điểm serve khởi động (bug ở write/edit hoặc project_dir
    # bị lệch), KHÔNG PHẢI lỗi ở chính http.server hay ở phía trình duyệt.
    try:
        listing = sorted(p.name + ("/" if p.is_dir() else "") for p in Path(run_cwd).iterdir())
        _serve_log(run_cwd, f"listing run_cwd TRƯỚC Popen: {listing}")
    except Exception as e:
        _serve_log(run_cwd, f"LỖI liệt kê run_cwd TRƯỚC Popen: {e!r}")
    # Check port có bị process LẠ (ngoài hệ thống serve:) chiếm sẵn không --
    # vd user/agent từng chạy tay 1 lệnh khác (node -e ..., server cũ) rồi
    # quên tắt, hoặc zombie sống sót qua lần app bị kill cứng trước đó. Nếu
    # không dọn, lệnh serve mới có thể bind fail HOẶC (tệ hơn, tuỳ OS) request
    # vẫn lọt vào process CŨ -- xem comment đầy đủ ở _serve_kill_port_owner.
    # _serve_kill_existing() ở trên chỉ dọn process serve: CŨ do CHÍNH hệ
    # thống này track (_serve_procs) -- không thấy được process lạ bên ngoài,
    # nên cần bước riêng này, độc lập, chạy SAU _serve_kill_existing.
    if guessed_port is not None:
        if not _serve_port_available(guessed_port):
            return (f"[serve] Port {guessed_port} đang do tiến trình khác sử dụng. "
                    "Không tự ý kill tiến trình ngoài; hãy chọn port khác hoặc tự dừng nó.")
    try:
        proc = subprocess.Popen(
            argv, shell=False, cwd=run_cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # process group riêng -- killpg dọn sạch cả cháu
        )
    except Exception as e:
        _serve_log(run_cwd, f"LỖI Popen: {e!r}")
        return f"[serve] Không khởi động được: {e}"
    time.sleep(0.3)  # khoảng lặng ngắn để bắt lỗi khởi động tức thì (vd port
    # đã bị chiếm bởi tiến trình KHÁC ngoài hệ thống serve này, hoặc lệnh sai
    # cú pháp thoát ngay) -- không phải chờ server "xong" (nó không bao giờ
    # xong), chỉ để phát hiện sớm trường hợp chết yểu rõ ràng.
    if proc.poll() is not None:
        code = proc.returncode
        _serve_log(run_cwd, f"Process THOÁT NGAY sau 0.3s, exit_code={code} -- "
                            f"có thể lệnh sai cú pháp hoặc port bị chiếm bởi "
                            f"process KHÁC (ngoài hệ thống serve).")
        return (f"[serve] Process thoát ngay (exit_code={code}) -- lệnh có thể sai "
                f"cú pháp hoặc port đã bị chương trình KHÁC (ngoài hệ thống serve) "
                f"chiếm. Lệnh: {inner_command}")
    _serve_procs[key] = {"proc": proc, "cmd": inner_command}
    _serve_log(run_cwd, f"Process sống, pid={proc.pid}, pgid={os.getpgid(proc.pid)!r}")
    replaced_note = f" (đã thay thế server cũ: {old_cmd})" if old_cmd else ""
    base_msg = (
        f"[serve] Đang chạy nền, pid={proc.pid}{replaced_note}.\n"
        f"Lệnh: {inner_command}\n"
        f"Thư mục: {run_cwd}\n"
        f"Server này sống cho tới khi bị thay thế bởi lệnh 'serve:' kế tiếp "
        f"(cùng project) -- không cần/không thể dùng bash thường để dừng nó."
    )
    # Auto-detect CHỈ áp dụng cho http.server (xem comment _serve_detect_entry_file
    # ở trên) -- lệnh khác (npm run dev, node...) không đoán được port/file thật,
    # trả về base_msg như cũ, không đổi hành vi.
    m_port = _HTTP_SERVER_RE.match(inner_command)
    if not m_port:
        _serve_log(run_cwd, "Lệnh không khớp _HTTP_SERVER_RE -- bỏ qua auto-detect, "
                            "trả base_msg nguyên bản.")
        return base_msg
    port = m_port.group(1) or "8000"  # http.server mặc định port 8000 nếu không truyền
    index_ok, suggested_file = _serve_detect_entry_file(run_cwd)
    _serve_log(run_cwd, f"_serve_detect_entry_file -> index_ok={index_ok} "
                        f"suggested_file={suggested_file!r} port={port}")
    if index_ok:
        # Có sẵn index.html -- http.server tự phục vụ đúng ở URL root, không
        # cần cảnh báo/gợi ý gì thêm.
        return base_msg
    if suggested_file is not None:
        url = f"http://localhost:{port}/{suggested_file}"
        _serve_log(run_cwd, f"Trả URL gợi ý: {url}")
        return (
            f"{base_msg}\n"
            f"URL đầy đủ (đã tự dò thấy đúng 1 file .html, không phải "
            f"\"index.html\" nên PHẢI có tên file trong URL, root sẽ 404 hoặc "
            f"liệt kê thư mục): {url}\n"
            f"Báo NGUYÊN VĂN URL này cho user, không rút gọn về dạng root "
            f"(http://localhost:{port}) -- http.server không tự suy ra file "
            f"khi không có index.html."
        )
    html_files = _serve_list_html_files(run_cwd)
    _serve_log(run_cwd, f"Không auto-pick được (mơ hồ) -- html_files={html_files}")
    if not html_files:
        return (
            f"{base_msg}\n"
            f"CẢNH BÁO: không tìm thấy file .html nào ở {run_cwd} -- nếu chưa "
            f"ghi file trang nào, hãy ghi trước; nếu file nằm trong thư mục con, "
            f"URL phải bao gồm cả đường dẫn con (vd http://localhost:{port}/sub/page.html)."
        )
    listed = ", ".join(html_files)
    return (
        f"{base_msg}\n"
        f"CẢNH BÁO: có {len(html_files)} file .html ở root ({listed}) và không "
        f"có \"index.html\" -- http.server sẽ không tự chọn đúng trang khi "
        f"user chỉ mở URL root (http://localhost:{port}). Phải nêu RÕ tên file "
        f"cụ thể trong URL báo cho user, vd http://localhost:{port}/{html_files[0]}."
    )

def _drain_process_stream(pipe, holder: dict, key: str, limit: int = 2 * 1024 * 1024):
    """Drain a subprocess pipe continuously while retaining bounded output."""
    half = max(1024, limit // 2)
    head = bytearray()
    tail = bytearray()
    total = 0
    try:
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8", errors="replace")
            total += len(chunk)
            if len(head) < half:
                take = min(half - len(head), len(chunk))
                head.extend(chunk[:take])
                chunk = chunk[take:]
            if chunk:
                tail.extend(chunk)
                if len(tail) > half:
                    del tail[:-half]
    except Exception as e:
        holder[key] = f"[stream read error: {e}]"
        return
    finally:
        try:
            pipe.close()
        except Exception:
            pass
    if total > limit:
        marker = f"[process output truncated: kept {limit:,} of {total:,} bytes]\n".encode()
        data = marker + bytes(head) + b"\n...\n" + bytes(tail)
    else:
        data = bytes(head) + bytes(tail)
    holder[key] = data.decode("utf-8", errors="replace")


def _run_bounded_capture(argv, timeout: int, cwd=None, limit: int = 2 * 1024 * 1024):
    """subprocess.run(capture_output=True) equivalent with bounded RAM."""
    proc = subprocess.Popen(argv, shell=False, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=cwd, start_new_session=True)
    captured = {}
    readers = [
        threading.Thread(target=_drain_process_stream,
                         args=(proc.stdout, captured, "stdout", limit), daemon=True),
        threading.Thread(target=_drain_process_stream,
                         args=(proc.stderr, captured, "stderr", limit), daemon=True),
    ]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    for reader in readers:
        reader.join(timeout=5)
    stdout = captured.get("stdout", "")
    stderr = captured.get("stderr", "")
    if timed_out:
        raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def tool_bash(command, timeout=30):
    if not isinstance(command, str):
        return "[error: command must be a string]"
    try:
        timeout = max(1, min(int(timeout), 3600))
    except (TypeError, ValueError):
        timeout = 30
    # Fast deny catches obviously dangerous text for both normal and serve mode;
    # the structured validator below enforces the complete command policy.
    if _BASH_DENY_RE.search(command):
        proj_hint = str(_project_dir.resolve()) if _project_dir is not None else os.getcwd()
        return (f"[policy] Lệnh nguy hiểm bị chặn.\n"
                f"Thư mục chạy dự kiến: {proj_hint}\n"
                f"Lệnh bị từ chối: {command[:200]}")

    # Nhánh serve dùng Popen nền nhưng vẫn phải qua validator. Trước đây
    # nhánh này bỏ qua allowlist, khiến "serve: <lệnh bất kỳ>" trở thành
    # đường chạy shell tự do dù process có thoát ngay sau đó.
    m = _SERVE_PREFIX_RE.match(command)
    if m:
        inner = command[m.end():]
        allowed, reason, serve_argv = _validate_bash_command(inner, for_serve=True)
        if not allowed:
            return f"[policy] serve command blocked.\nLý do: {reason}"
        return tool_bash_serve(inner, serve_argv)

    allowed, reason, argv = _validate_bash_command(command)
    if not allowed:
        return (
            "[policy] bash command blocked by allowlist.\n"
            f"Lý do: {reason}\n"
            "Dùng tool read/write/edit/delete/glob/grep khi command không được phép."
        )
    if _project_dir is not None:
        proj = _project_dir.resolve()

        # NOTE: deny-check đã chuyển lên đầu hàm (áp dụng chung cho serve +
        # bash thường) — không lặp lại ở đây nữa.

        # Chạy trong project_dir, không phải cwd tuỳ tiện.
        run_cwd = str(proj)
    else:
        run_cwd = os.getcwd()

    started = time.time()
    try:
        proc = subprocess.Popen(argv, shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=run_cwd,
                                start_new_session=True)
        captured = {}
        readers = [
            threading.Thread(target=_drain_process_stream,
                             args=(proc.stdout, captured, "stdout"), daemon=True),
            threading.Thread(target=_drain_process_stream,
                             args=(proc.stderr, captured, "stderr"), daemon=True),
        ]
        for reader in readers:
            reader.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
        for reader in readers:
            reader.join(timeout=5)
        stdout = captured.get("stdout", "")
        stderr = captured.get("stderr", "")
        elapsed = time.time() - started
        code = 124 if timed_out else (proc.returncode if proc.returncode is not None else 1)
        return _format_bash_result(command, code, stdout, stderr, elapsed,
                                   timed_out=timed_out,
                                   timeout=timeout if timed_out else None,
                                   run_cwd=run_cwd)
    except Exception as e:
        return f"[error: {e}]"

def _tail_text(text: str, limit: int = 4000) -> str:
    """Keep bash output useful without flooding context."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    half = max(200, limit // 2)
    return text[:half] + f"\n... [truncated {len(text)-limit} chars] ...\n" + text[-half:]

def _classify_bash_error(code: int, stderr: str, stdout: str,
                         timed_out: bool = False) -> tuple[str, str]:
    text = f"{stderr}\n{stdout}".lower()
    if timed_out:
        return "timeout", "Retry only with a longer timeout or a narrower command."
    if code == 0:
        return "ok", "No retry needed."
    if code == 127 or "not found" in text or "command not found" in text:
        return "missing_command", "Check installed tools or use an available alternative."
    if code == 126 or "permission denied" in text:
        return "permission", "Fix permissions or choose a command that does not need elevated access."
    if "no such file or directory" in text or "cannot find" in text:
        return "missing_path", "Verify the path with read/glob before retrying."
    if "syntax error" in text or "unexpected token" in text:
        return "shell_syntax", "Fix quoting/shell syntax before retrying."
    if "network is unreachable" in text or "temporary failure" in text or "could not resolve" in text:
        return "network", "Retry only if network access is expected to work."
    if "test failed" in text or "failed" in text or "assert" in text:
        return "test_failure", "Inspect the failing test/error and change code before retrying."
    return "nonzero_exit", "Do not retry unchanged; inspect stderr/stdout first."

def _format_bash_result(command: str, code: int, stdout: str, stderr: str,
                        elapsed: float, timed_out: bool = False,
                        timeout: int | None = None, run_cwd: str | None = None) -> str:
    error_class, retry_hint = _classify_bash_error(code, stderr, stdout, timed_out)
    status = "timeout" if timed_out else ("ok" if code == 0 else "error")
    lines = [
        "[bash diagnostic]",
        f"status: {status}",
        f"exit_code: {code}",
        f"duration: {elapsed:.2f}s",
        f"cwd: {run_cwd or os.getcwd()}",
        f"error_class: {error_class}",
        f"retry_hint: {retry_hint}",
    ]
    if timeout is not None:
        lines.append(f"timeout: {timeout}s")
    if stdout.strip():
        lines.append("\n[stdout]")
        lines.append(_tail_text(stdout.rstrip()))
    if stderr.strip():
        lines.append("\n[stderr]")
        lines.append(_tail_text(stderr.rstrip()))
    if not stdout.strip() and not stderr.strip():
        lines.append("\n(no output)")
    return "\n".join(lines)


def _dir_tree(path: Path, prefix="", depth=0, max_depth=4, max_entries=200, _count=None):
    """Render a recursive directory tree. Returns list of lines."""
    if _count is None:
        _count = [0]
    if depth > max_depth or _count[0] >= max_entries:
        return []
    lines = []
    try:
        entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        return [f"{prefix}[permission denied]"]
    # Skip common noise dirs
    SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
            ".pytest_cache", "dist", "build", ".next", ".nuxt", FW_DATA_NAME}
    visible = [e for e in entries if e.name not in SKIP and not e.name.startswith(".")]
    for i, entry in enumerate(visible):
        if _count[0] >= max_entries:
            lines.append(f"{prefix}... (truncated)")
            break
        connector = "└── " if i == len(visible) - 1 else "├── "
        if entry.is_symlink():
            lines.append(f"{prefix}{connector}{entry.name} -> [symlink skipped]")
            _count[0] += 1
            continue
        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            _count[0] += 1
            extension = "    " if i == len(visible) - 1 else "│   "
            lines.extend(_dir_tree(entry, prefix + extension, depth + 1,
                                   max_depth, max_entries, _count))
        else:
            size = ""
            try:
                sz = entry.stat().st_size
                size = f"  {DIM}({sz:,}b){R}" if sz > 0 else ""
            except Exception:
                pass
            lines.append(f"{prefix}{connector}{entry.name}{size}")
            _count[0] += 1
    return lines

# ── Tool output limits ───────────────────────────────────────────────────────
# Model sees this much per tool call. Head+tail strategy like openai/codex.
# (Tham khảo openai/codex issue #6426: line-based cap không phản ánh đúng áp
# lực token thật — 2 lần đọc cùng số dòng có thể lệch token vài lần tùy độ
# dày file. Codex đã chuyển sang cap theo ước lượng token/byte thực tế thay
# vì 1 số dòng cố định. Áp dụng tương tự ở đây cho riêng `read`: cap ký tự
# co giãn theo `limit` dòng model thực sự xin, thay vì 1 hằng số tĩnh chung
# cho mọi tool — tránh 2 lỗi đối lập: đọc ít dòng vẫn bị buộc chung 1 ngưỡng
# lớn (lãng phí context), hoặc đọc nhiều dòng bị cắt giữa oan dù đã qua gate
# hard-block riêng của `read`.)
TOOL_OUTPUT_MAX_CHARS   = 12_000   # ~3k tokens — cap CHUNG cho tool khác (bash/grep/glob/...), không đổi
TOOL_HISTORY_MAX_CHARS  = 3_000    # ~500 tokens — what stays in context forever (không đổi, không liên quan limit đọc)
TOOL_KEEP_FULL_TURNS    = 4        # giữ tool_result đầy đủ cho N turn gần nhất
READ_DEFAULT_LIMIT      = 80       # lines, down from 200
READ_LIMIT_MAX          = 700      # hard-block cứng cho tool `read` (xem tool_read)
READ_CHARS_PER_LINE_EST = 90       # ước lượng ký tự/dòng kèm overhead (số dòng + tab + code) — đo thực nghiệm trên codebase thật (avg ~54 chars/line nội dung thô + prefix "N\t") rồi làm tròn lên cho biên an toàn
READ_OUTPUT_MIN_CHARS   = TOOL_OUTPUT_MAX_CHARS  # sàn: không bao giờ thấp hơn cap chung, kể cả khi limit nhỏ
READ_OUTPUT_MAX_CHARS   = 90_000   # ~22k tokens — trần an toàn tuyệt đối cho read, kể cả limit=700 trên file dòng cực dài

def _read_output_cap(limit: int) -> int:
    """Cap ký tự cho output của `read`, co giãn theo số dòng thực xin.

    Không dùng 1 hằng số tĩnh cho mọi lần gọi (đọc 20 dòng và đọc 700 dòng
    không nên chịu chung ngưỡng) — nhưng vẫn có sàn (không thấp hơn cap tool
    thường) và trần (không vượt READ_OUTPUT_MAX_CHARS dù limit=700 trên file
    toàn dòng cực dài, ví dụ minified/generated code).
    """
    try:
        if isinstance(limit, bool):
            raise ValueError
        limit = int(limit)
    except (TypeError, ValueError):
        limit = READ_DEFAULT_LIMIT
    limit = max(1, min(limit, READ_LIMIT_MAX))
    est = limit * READ_CHARS_PER_LINE_EST
    return max(READ_OUTPUT_MIN_CHARS, min(est, READ_OUTPUT_MAX_CHARS))

def _head_tail(text: str, max_chars: int, label="tool output") -> str:
    """Keep head + tail, drop middle. Model knows exactly what was cut."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    head = text[:half]
    tail = text[-half:]
    cut  = len(text) - max_chars
    return f"{head}\n\n... [{cut:,} chars omitted from middle of {label}] ...\n\n{tail}"

def _tool_known_args(name: str, args: dict) -> dict:
    """Return only arguments declared by the local tool schema.

    MCP schemas are dynamic and keep their complete argument object. Local
    dispatch ignores unknown keys, so signatures must ignore them too.
    """
    if not isinstance(args, dict) or name.startswith("mcp__"):
        return dict(args) if isinstance(args, dict) else {}
    for spec in globals().get("TOOLS", []):
        fn = spec.get("function", {}) if isinstance(spec, dict) else {}
        if fn.get("name") == name:
            properties = (fn.get("parameters") or {}).get("properties") or {}
            return {key: value for key, value in args.items() if key in properties}
    return dict(args)


def _history_tool_call_key(name: str, args: dict) -> tuple | None:
    """Canonical key for history dedup.

    Dedup must describe the complete query, not merely the target path. Reads
    at different offsets, grep calls with different patterns, and different
    symbols in one file are distinct evidence and must remain distinct.
    """
    if name not in {"read", "grep", "glob", "view_symbol", "delegate"}:
        return None
    try:
        normalized = _tool_known_args(name, args)
        if name == "read":
            normalized.setdefault("offset", 1)
            normalized.setdefault("limit", READ_DEFAULT_LIMIT)
            normalized.setdefault("depth", 4)
        elif name == "glob":
            normalized["cwd"] = normalized.get("cwd") or "."
        elif name == "grep":
            defaults = {
                "path": None, "glob": None, "ignore_case": False,
                "fixed_string": False, "invert": False, "word": False,
                "context": 0, "max_count": None, "files_only": False,
                "multiline": False,
            }
            for field, value in defaults.items():
                normalized.setdefault(field, value)
        elif name == "delegate":
            # A delegate is a semantic request; only an exact same request is
            # safe to suppress. Different instructions may intentionally ask
            # for a second independent review of the same files.
            _resolve_steps = globals().get("_resolve_subagent_max_steps")
            _max_steps = normalized.get("max_steps")
            if callable(_resolve_steps):
                _max_steps = _resolve_steps(_max_steps)
            _canonical_path = globals().get("_canonical_runtime_path")
            _target_files = normalized.get("target_files") or []
            if callable(_canonical_path):
                _target_files = [_canonical_path(path) for path in _target_files]
            normalized = {
                "task_type": normalized.get("task_type"),
                "instruction": normalized.get("instruction") or "",
                "expected_output": normalized.get("expected_output") or "",
                "target_files": sorted(set(_target_files)),
                "target_location": normalized.get("target_location") or "",
                "tools": sorted(set(normalized.get("tools") or [])),
                "max_steps": _max_steps,
            }
        # History keys must identify the actual file, not the spelling used by
        # the model.  ``foo.py`` and ``./foo.py`` (or a project-name prefix)
        # therefore share evidence, while invalid paths simply fall back to
        # no history key instead of making an unsafe guess.
        if name in {"read", "grep", "view_symbol"}:
            raw_path = normalized.get("path")
            if name == "grep" and not raw_path:
                raw_path = "."
            if raw_path:
                normalized["path"] = str(_resolve_read_path(raw_path))
        elif name == "glob" and normalized.get("cwd"):
            normalized["cwd"] = str(_resolve_read_path(normalized["cwd"]))
        canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return name, canonical


def _compact_heavy_tool_call(tc: dict) -> dict:
    """Strip large replay-unsafe payloads from an old tool call."""
    name = tc.get("function", {}).get("name", "")
    if name not in {
        "write", "multiedit", "apply_patch", "edit", "todowrite",
        "task", "delegate", "question",
    }:
        return tc
    try:
        args = json.loads(tc["function"]["arguments"])
        changed = False
        placeholder = _HISTORY_COMPACTED_MARKER
        for field in (
            "content", "patch", "old_str", "new_str", "todos",
            "description", "instruction", "expected_output", "question",
        ):
            if field in args:
                args[field] = placeholder
                changed = True
        for edit_item in args.get("edits", []):
            if isinstance(edit_item, dict):
                for field in ("old_str", "new_str"):
                    if field in edit_item:
                        edit_item[field] = placeholder
                        changed = True
        if changed:
            return {
                **tc,
                "function": {
                    **tc["function"],
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return tc


def _prune_tool_results(messages: list, keep_full_turns: int | None = None) -> list:
    """
    Giảm token tool_result trong context:
    1. Stub các tool_result cũ hơn keep_full_turns
    2. Dedup exact read/glob/grep/view_symbol calls; distinct ranges, patterns
       and symbols are never merged merely because they share a path.
    """
    if keep_full_turns is None:
        keep_full_turns = TOOL_KEEP_FULL_TURNS
    keep_full_turns = max(0, int(keep_full_turns))
    # ── Bước 1: xác định groups (assistant+tool_calls → tool_results) ─────────
    groups = []
    i = 0
    while i < len(messages):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            j = i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                j += 1
            if j > i + 1:
                groups.append((i + 1, j - 1))
            i = j
        else:
            i += 1

    # Stub các group cũ
    if keep_full_turns == 0:
        old_groups = groups
    else:
        old_groups = groups[:-keep_full_turns] if len(groups) > keep_full_turns else []
    stub_indices = set()
    for start, end in old_groups:
        for idx in range(start, end + 1):
            stub_indices.add(idx)

    # ── Bước 2: dedup exact read/glob/grep/view_symbol calls ─────────────────
    # Map tool_call_id → canonical full-query key. Using only path here loses
    # evidence from a different read range, grep pattern or symbol.
    tc_id_to_key: dict[str, tuple] = {}
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                name = tc.get("function", {}).get("name", "")
                args_raw = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}
                key = _history_tool_call_key(name, args)
                if key is not None:
                    tc_id_to_key[tc.get("id", "")] = key

    # Duyệt ngược: exact call mới nhất giữ đầy đủ, bản exact cũ hơn → stub.
    # A canonical query alone is not enough for a read: the same call can
    # legitimately return a new file version after an external edit. Keep a
    # small set of result markers per key so only byte-identical evidence is
    # collapsed.
    def _result_marker(message: dict, key: tuple):
        content = str(message.get("content", ""))
        if key and key[0] == "read":
            version_match = re.search(
                r"(?:^|\n)Version:\s*([0-9a-f]{32})\b", content, re.IGNORECASE
            )
            if version_match:
                return ("version", version_match.group(1).lower())
        return ("content", _content_hash(content))

    seen_file_tool: dict[tuple, set[tuple]] = {}
    dedup_stub: set[int] = set()
    for idx in range(len(messages) - 1, -1, -1):
        m = messages[idx]
        if m.get("role") != "tool":
            continue
        tc_id = m.get("tool_call_id", "")
        key = tc_id_to_key.get(tc_id)
        if key is None:
            continue
        marker = _result_marker(m, key)
        markers = seen_file_tool.setdefault(key, set())
        if marker in markers:
            dedup_stub.add(idx)
        else:
            markers.add(marker)

    # ── Bước 3: dedup range chồng lấn cho `read` cùng path ────────────────────
    # Bước 2 chỉ bắt exact-match tham số. Nhưng thực tế AI thường đọc cùng
    # 1 file nhiều lần với offset/limit HƠI khác nhau (dò gate verify, đọc
    # tiếp phần kế — offset=1,limit=80 rồi offset=1,limit=150...) — đây là
    # 2 key khác nhau ở bước 2 nên KHÔNG bị dedup, dù range dòng đọc được
    # gần như trùng lặp hoàn toàn. Ở đây so sánh theo [offset, offset+limit)
    # thật: nếu 1 lần đọc SAU (mới hơn) có range bao trọn 1 lần đọc TRƯỚC
    # (cũ hơn) trên CÙNG path, bản cũ chỉ còn là tập con thông tin của bản
    # mới → stub bản cũ. Range lệch nhau (không bao trọn) vẫn giữ nguyên cả
    # hai, vì có thể là 2 đoạn thật sự khác nhau của file.
    read_ranges: list[tuple[int, str, int, int, str]] = []  # (idx,path,start,end,version)
    for m_idx, m in enumerate(messages):
        if m.get("role") != "tool":
            continue
        key = tc_id_to_key.get(m.get("tool_call_id", ""))
        if key is None or key[0] != "read":
            continue
        try:
            normalized = json.loads(key[1])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        path = normalized.get("path")
        if path is None:
            continue
        # Use the *delivered* line range and content version, not the
        # requested limit.  `read` may soft-truncate a whole-file request to
        # 80 lines, and a later version of the same path must never erase
        # evidence from the earlier version.
        content = str(m.get("content", ""))
        line_match = re.search(
            r"(?:^|\n)Lines\s+(\d+)-(\d+)\s+of\s+\d+", content
        )
        version_match = re.search(
            r"(?:^|\n)Version:\s*([0-9a-f]{32})\b", content, re.IGNORECASE
        )
        if not line_match or not version_match:
            continue
        start = int(line_match.group(1))
        end = int(line_match.group(2)) + 1  # inclusive output → half-open range
        version = version_match.group(1).lower()
        read_ranges.append((m_idx, path, start, end, version))

    range_stub: set[int] = set()
    # So từng cặp theo cùng path; vì read_ranges đã theo thứ tự message
    # (tăng dần idx = tăng dần thời gian), "sau" luôn ở vị trí j > i.
    for i in range(len(read_ranges)):
        idx_i, path_i, s_i, e_i, version_i = read_ranges[i]
        if idx_i in stub_indices or idx_i in range_stub:
            continue  # đã bị stub lý do khác, khỏi so tiếp cho nhanh
        for j in range(i + 1, len(read_ranges)):
            idx_j, path_j, s_j, e_j, version_j = read_ranges[j]
            if path_j != path_i:
                continue
            if version_j != version_i:
                continue
            if s_j <= s_i and e_j >= e_i:
                # bản sau (j) bao trọn bản trước (i) → bản trước thừa
                range_stub.add(idx_i)
                break

    # ── Áp dụng stub ─────────────────────────────────────────────────────────
    all_stub = stub_indices | dedup_stub | range_stub
    if not all_stub:
        return messages

    result = []
    for idx, m in enumerate(messages):
        if idx in all_stub and m.get("role") == "tool":
            c = m.get("content", "")
            half = TOOL_HISTORY_MAX_CHARS // 2
            stub = (c[:half] + "\n…\n" + c[-half:]) if len(c) > TOOL_HISTORY_MAX_CHARS else c
            result.append({**m, "content": stub})
        else:
            result.append(m)

    # ── Strip heavy content từ assistant tool_call arguments ─────────────────
    # write/multiedit/apply_patch/edit lưu full content trong arguments →
    # nằm mãi trong history nếu không strip → phình token mỗi step.
    # Chỉ strip các turn cũ (ngoài TOOL_KEEP_FULL_TURNS gần nhất).
    # Tìm index của assistant message thuộc các group cũ
    old_assistant_indices: set[int] = set()
    for start, end in old_groups:
        # assistant message ngay trước group (start-1)
        ai_idx = start - 1
        if ai_idx >= 0:
            old_assistant_indices.add(ai_idx)

    stripped_result = []
    for idx, m in enumerate(result):
        if idx in old_assistant_indices and m.get("role") == "assistant" and m.get("tool_calls"):
            new_tcs = [_compact_heavy_tool_call(tc) for tc in m["tool_calls"]]
            if new_tcs != m["tool_calls"]:
                m = {**m, "tool_calls": new_tcs}
        stripped_result.append(m)

    return stripped_result


# ── delegate: nén sớm hơn cho kết quả "delegate" trong context AGENT CHÍNH ──
# _prune_tool_results ở trên xử lý keep_full_turns THEO TOÀN BỘ mảng messages
# 1 lượt — không có chỗ để "1 tool cụ thể có ngưỡng tuổi riêng" trong chính
# hàm đó (group = 1 assistant tool_calls + mọi tool_result theo sau nó, bất
# kể tool gì trong group). Không sửa hàm gốc (dùng chung cho MỌI tool, rủi ro
# cao); thay vào đó, hàm RIÊNG này chạy SAU _prune_tool_results, chỉ quét các
# message role="tool" mà content bắt đầu bằng "[delegate:" (output contract
# ép ở _tool_delegate_inner, 08_undo_dispatch.py — luôn đúng prefix nhờ lớp
# bảo hiểm ở đó) và áp ngưỡng tuổi RIÊNG, ngắn hơn mặc định — vì bản chất
# việc "delegate" giao đã CHỐT xong khi model chính đọc lần đầu, không cần
# tra lại nhiều lần như đọc file.
DELEGATE_KEEP_FULL_TURNS = 2   # ngắn hơn TOOL_KEEP_FULL_TURNS=4 mặc định

def _prune_delegate_results(messages: list, keep_full_turns: int | None = None) -> list:
    """Stub các tool_result của "delegate" cũ hơn keep_full_turns GROUP gần
    nhất (group tính theo đúng định nghĩa ở _prune_tool_results: 1 assistant
    tool_calls + các tool_result theo sau). Không đụng tool_result của tool
    khác trong CÙNG group đó — chỉ message nào thật sự có content bắt đầu
    bằng "[delegate:" mới bị stub."""
    if keep_full_turns is None:
        keep_full_turns = DELEGATE_KEEP_FULL_TURNS
    keep_full_turns = max(0, int(keep_full_turns))

    # Xác định group theo đúng logic bước 1 của _prune_tool_results, nhưng
    # chỉ đếm group nào CHỨA ít nhất 1 tool_result "delegate" — 1 group toàn
    # đọc file/grep không tính vào "N group delegate gần nhất".
    delegate_groups = []  # list[(start, end)] các group có >=1 message delegate
    i = 0
    while i < len(messages):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            j = i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                j += 1
            if j > i + 1:
                has_delegate = any(
                    str(messages[k].get("content", "")).startswith("[delegate:")
                    for k in range(i + 1, j)
                )
                if has_delegate:
                    delegate_groups.append((i + 1, j - 1))
            i = j
        else:
            i += 1

    old_delegate_groups = (delegate_groups[:-keep_full_turns]
                            if len(delegate_groups) > keep_full_turns else [])
    if keep_full_turns == 0:
        old_delegate_groups = delegate_groups
    if not old_delegate_groups:
        return messages

    stub_indices = set()
    for start, end in old_delegate_groups:
        for idx in range(start, end + 1):
            if str(messages[idx].get("content", "")).startswith("[delegate:"):
                stub_indices.add(idx)

    result = []
    for idx, m in enumerate(messages):
        if idx in stub_indices:
            c = m.get("content", "")
            half = TOOL_HISTORY_MAX_CHARS // 2
            stub = (c[:half] + "\n…\n" + c[-half:]) if len(c) > TOOL_HISTORY_MAX_CHARS else c
            result.append({**m, "content": stub})
        else:
            result.append(m)
    return result


# ── Per-session file index ───────────────────────────────────────────────────
def _index_key() -> str:
    """Stable workspace key so sessions sharing a project also share its index."""
    return str(_workspace_root())

def _fw_data_dir() -> Path:
    """
    <cwd>/.fw_data/ — thư mục ẩn lưu index cạnh project.
    Tên bắt đầu '.' → hidden trên Linux.
    KHÔNG xuất hiện trong bất kỳ tool nào (glob/grep/read/dir_tree).
    """
    d = Path.cwd() / FW_DATA_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def _index_path() -> Path:
    """<cwd>/.fw_data/index_<sid>.json — lưu cạnh project, ẩn khỏi mọi tool.
    FIX (bug #6): trước đây file là <cwd>/.fw_data/index.json dùng CHUNG cho
    mọi session trong cùng cwd, dù docstring/comment khẳng định "Per-session
    file index". Nhưng key bên trong dict (xem _index_update) được tính theo
    _workspace_root() — là sandbox RIÊNG từng session (cwd/<sid>). Hệ quả: 2
    session khác nhau cùng cwd, nếu có file trùng tên tương đối (vd "foo.py"),
    session chạy sau sẽ ghi đè entry "foo.py" của session chạy trước trong
    cùng 1 file JSON, dù 2 file vật lý hoàn toàn khác nhau (sidA/foo.py vs
    sidB/foo.py) — session trước "mất" index dù file vẫn còn nguyên trên đĩa.
    Giờ tách file theo sid: mỗi session ghi vào index_<sid>.json riêng, không
    còn đụng nhau. Fallback "index.json" (không sid) chỉ dùng khi chưa có sid
    nào active (vd gọi ngoài luồng agent_turn bình thường).
    """
    digest = hashlib.sha256(_index_key().encode()).hexdigest()[:16]
    fname = f"index_workspace_{digest}.json"
    return _fw_data_dir() / fname

def _index_load() -> dict:
    """Load index cho project hiện tại. Trả về {} nếu chưa có.
    Migrate-on-read: nếu file theo-sid chưa tồn tại nhưng index.json cũ
    (không sid, từ trước khi fix bug #6) có entry thuộc workspace hiện tại,
    import các entry đó vào lần đầu để không mất dữ liệu cũ của user."""
    p = _index_path()
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    # Migrate-on-read từ index.json cũ (chung, trước bug-fix) nếu có
    # BUG FIX: trước dùng root = _workspace_root(), nhưng _workspace_root()
    # rơi về Path.cwd() khi còn placeholder — cwd là thư mục CHA chứa TẤT CẢ
    # session con (mỗi session một subdir theo sid), nên "thuộc workspace
    # hiện tại" khi đó thực chất nghĩa là "thuộc BẤT KỲ session nào cùng cwd".
    # Hậu quả: migrate kéo cả entry của session khác (đã từng ghi vào
    # index.json chung trước khi có fix per-sid) vào index của session mới,
    # rồi tool_file_index() có thể hiện thẳng ra ngoài. Giờ luôn dùng
    # _project_dir thật của CHÍNH session này (có sẵn từ session_create,
    # kể cả khi còn placeholder) làm mốc — không bao giờ nới lỏng ra cwd.
    if _project_dir_sid:
        legacy = _fw_data_dir() / "index.json"
        if legacy.exists():
            try:
                legacy_index = json.loads(legacy.read_text())
                root = _project_dir.resolve() if _project_dir is not None else _workspace_root()
                migrated = {
                    k: v for k, v in legacy_index.items()
                    if Path(v.get("path", "")).resolve().is_relative_to(root)
                }
                if migrated:
                    _index_save(migrated)
                    return migrated
            except Exception:
                pass
    return {}

def _index_save(index: dict):
    """Ghi index ra disk."""
    try:
        _index_path().write_text(json.dumps(index, ensure_ascii=False))
    except Exception:
        pass

def _index_update(abs_path: str, content: str, symbols: dict):
    """Thêm/update entry cho file vào index của project."""
    index = _index_load()
    root = _workspace_root()
    try:
        rel = str(Path(abs_path).resolve().relative_to(root))
    except ValueError:
        rel = Path(abs_path).name
    sym_map = {name: s["line"] for name, s in symbols.items()}
    index[rel] = {
        "path": str(Path(abs_path).resolve()),
        "lines": len(content.splitlines()),
        "symbols": sym_map,
        "mtime_ns": Path(abs_path).stat().st_mtime_ns if Path(abs_path).exists() else 0,
        "size": Path(abs_path).stat().st_size if Path(abs_path).exists() else len(content),
    }
    _index_save(index)

def _index_prune():
    """Xóa entry file không còn tồn tại trên disk."""
    index = _index_load()
    pruned = {k: v for k, v in index.items() if Path(v["path"]).exists()}
    if len(pruned) != len(index):
        _index_save(pruned)

def tool_file_index() -> str:
    """Trả về symbol index của project hiện tại."""
    index = _index_load()
    # Refresh lazily from disk so this tool is useful before the first read and
    # never advertises stale symbols after an external edit.
    for p in _workspace_reference_files(max_files=400):
        try:
            st = p.stat()
            rel = str(p.resolve().relative_to(_workspace_root()))
            old = index.get(rel, {})
            if old.get("mtime_ns") == st.st_mtime_ns and old.get("size") == st.st_size:
                continue
            if st.st_size > 2 * 1024 * 1024:
                continue
            content = p.read_text(errors="replace")
            index[rel] = {
                "path": str(p.resolve()), "lines": len(content.splitlines()),
                "symbols": {n: s["line"] for n, s in _parse_symbols(content, p.suffix).items()},
                "mtime_ns": st.st_mtime_ns, "size": st.st_size,
            }
        except Exception:
            continue
    valid = {k: v for k, v in index.items() if Path(v.get("path", "")).exists()}
    if valid != index:
        index = valid
    _index_save(index)

    # BUG FIX: filter cũ chỉ chạy `if not _project_dir_is_placeholder` — nghĩa
    # là TẮT HẲN đúng lúc rủi ro cao nhất. Ở placeholder mode, _check_sandbox_read
    # cho phép đọc BẤT KỲ path nào trên toàn filesystem (xem _check_sandbox_read),
    # nên index lúc đó có thể chứa path/symbol của file NGOÀI project (thậm chí
    # ngoài mọi khái niệm sandbox), hoặc entry của session khác migrate từ
    # index.json cũ. Cũ: chỉ lọc SAU khi sandbox đã enforce — tức lúc index gần
    # như chỉ còn chứa file hợp lệ rồi, filter thành thừa. Giờ: LUÔN lọc, và mốc
    # "trong project" luôn là _project_dir thật (kể cả khi còn placeholder) —
    # không bao giờ nới lỏng thành Path.cwd(), vì cwd có thể chứa nhiều
    # session/sub-project khác nằm cạnh nhau.
    if _project_dir is not None:
        proj = _project_dir.resolve()
        filtered = {}
        for k, v in index.items():
            try:
                if Path(v["path"]).resolve().is_relative_to(proj):
                    filtered[k] = v
            except Exception:
                continue
        index = filtered
    else:
        # Chưa hề có _project_dir nào được gán (state bất thường) — an toàn
        # nhất là không hiện gì, tránh lộ index rỗng-context không rõ nguồn.
        index = {}

    if not index:
        return "(no project files indexed yet)"
    lines = [f"File index for project '{_index_key()}' ({len(index)} files):"]
    for rel, info in sorted(index.items()):
        syms = info.get("symbols", {})
        lc   = info.get("lines", "?")
        if syms:
            sym_str = ", ".join(f"{n}@{ln}" for n, ln in list(syms.items())[:20])
            if len(syms) > 20:
                sym_str += f" (+{len(syms)-20} more)"
            lines.append(f"  {rel} ({lc} lines): {sym_str}")
        else:
            lines.append(f"  {rel} ({lc} lines)")
    return "\n".join(lines)

_REFERENCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".css", ".scss", ".sass", ".less", ".json", ".md",
}

def _workspace_root() -> Path:
    if _project_dir is not None:
        return _project_dir.resolve()
    return Path.cwd().resolve()

def _workspace_reference_files(seed_file: str | None = None, max_files: int = 400) -> list[Path]:
    """Return likely source files for references without depending on external LSP."""
    root = _workspace_root()
    files: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path):
        try:
            p = path.expanduser().resolve()
        except Exception:
            return
        if not p.exists() or not p.is_file() or p.suffix.lower() not in _REFERENCE_EXTS:
            return
        try:
            if p.stat().st_size > 20 * 1024 * 1024:
                return
        except OSError:
            return
        try:
            p.relative_to(root)
        except ValueError:
            return
        key = str(p)
        if key not in seen:
            seen.add(key)
            files.append(p)

    if seed_file:
        _add(Path(seed_file))

    index = _index_load()
    for info in index.values():
        _add(Path(info.get("path", "")))
        if len(files) >= max_files:
            return files[:max_files]

    skip = {".git", FW_DATA_NAME, "__pycache__", "node_modules", ".venv", "venv",
            ".mypy_cache", ".pytest_cache", "dist", "build", ".next", ".nuxt"}
    try:
        for p in root.rglob("*"):
            if len(files) >= max_files:
                break
            if any(part in skip for part in p.parts):
                continue
            _add(p)
    except Exception:
        pass
    return files[:max_files]

def _references_in_python(path: Path, name: str) -> list[tuple[int, str]]:
    """AST-backed Python references with regex fallback for syntax errors."""
    import ast as _ast
    try:
        if path.stat().st_size > 20 * 1024 * 1024:
            return []
        src = path.read_text(errors="replace")
    except Exception:
        return []
    lines = src.splitlines()
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return [(i, l.strip()) for i, l in enumerate(lines, 1)
                if re.search(rf"\b{re.escape(name)}\b", l)]

    hit_lines: set[int] = set()
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.Name, _ast.arg)) and getattr(node, "id", getattr(node, "arg", "")) == name:
            hit_lines.add(node.lineno)
        elif isinstance(node, _ast.Attribute) and node.attr == name:
            hit_lines.add(node.lineno)
        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)) and node.name == name:
            hit_lines.add(node.lineno)
    return [(i, lines[i-1].strip()) for i in sorted(hit_lines) if 1 <= i <= len(lines)]

def _workspace_references(name: str, seed_file: str | None = None,
                          max_hits: int = 120) -> str:
    if not name:
        return "[lsp] No symbol at cursor"
    files = _workspace_reference_files(seed_file)
    hits: list[tuple[Path, int, str]] = []
    word_re = re.compile(rf"\b{re.escape(name)}\b")
    for p in files:
        if len(hits) >= max_hits:
            break
        if p.suffix.lower() == ".py":
            refs = _references_in_python(p, name)
        else:
            try:
                if p.stat().st_size > 20 * 1024 * 1024:
                    continue
                lines = p.read_text(errors="replace").splitlines()
            except Exception:
                continue
            refs = [(i, l.strip()) for i, l in enumerate(lines, 1) if word_re.search(l)]
        for ln, text in refs:
            hits.append((p, ln, text[:120]))
            if len(hits) >= max_hits:
                break
    if not hits:
        return f"[lsp] No references to `{name}` found in workspace ({len(files)} files scanned)"
    out = [f"References to `{name}` in workspace ({len(hits)} hits, {len(files)} files scanned):"]
    root = _workspace_root()
    for p, ln, text in hits:
        try:
            rel = str(p.resolve().relative_to(root))
        except ValueError:
            rel = str(p)
        out.append(f"  {rel}:{ln}: {text}")
    if len(hits) >= max_hits:
        out.append(f"  ... truncated at {max_hits} hits")
    return "\n".join(out)

def tool_read(path, offset=1, limit=READ_DEFAULT_LIMIT, depth=4, state=None):
    if not isinstance(path, str):
        return "[error: path must be a string]"
    # The JSON schema declares integers, but providers can still send booleans
    # or numeric strings.  Coercing those silently changes the requested range
    # (True→1, "10"→10) and makes policy/audit output misleading; reject them
    # before resolving or touching the filesystem.
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in (offset, limit, depth)):
        return "[error: offset, limit and depth must be integers]"
    if offset < 1:
        return "[error: offset must be at least 1]"
    if limit < 1:
        return "[error: limit must be at least 1]"
    if limit > READ_LIMIT_MAX:
        return (f"[policy] limit={limit} quá lớn (tối đa {READ_LIMIT_MAX}).\n"
                "Dùng grep/view_symbol để thu hẹp vị trí trước.")
    if depth < 0 or depth > 20:
        return "[error: depth must be between 0 and 20]"
    p = _resolve_read_path(path)
    err = _check_sandbox_read(str(p))
    if err: return err
    if not p.exists(): return f"[not found: {path}]"
    if p.is_dir():
        lines = [f"{p.resolve()}/"]
        lines += _dir_tree(p, "", max_depth=depth)
        count = sum(1 for l in lines if not l.endswith("/") and "..." not in l)
        lines.append(f"\n({count} files shown, depth={depth})")
        return "\n".join(lines)

    # B4 FIX: _recent_writes trước đây chỉ được .add()/.clear(), không bao giờ
    # được đọc — comment "block read-after-write" không có tác dụng thật.
    # Enforce mềm: nếu file vừa được write/edit trong turn này (đã có sẵn
    # trong _file_cache, đúng nội dung mới nhất), trả thẳng từ cache kèm
    # cảnh báo, không đọc lại disk — tiết kiệm 1 tool-call thật như rule
    # "Re-read after edit = FORBIDDEN" trong system prompt đã yêu cầu.
    resolved_key = str(p.resolve())
    # FIX (bug #7): trước đây nhánh này (a) không gọi _cache_invalidate() nên
    # có thể trả về nội dung CŨ nếu file bị sửa từ bên ngoài app (process khác,
    # user tự sửa tay, git checkout...) ngay sau write/edit gần nhất nhưng
    # trước khi _cache_validate_all() chạy lại (nó chỉ chạy lazy, sau bước có
    # write — xem 09_api_system.py); và (b) không cập nhật _file_read_time,
    # khiến edit's version-safety check (tool_edit) dùng observation lỗi thời
    # nếu thứ tự gọi đổi trong tương lai. Giờ luôn validate cache bằng hash
    # trước khi quyết định dùng, và luôn cập nhật read-time khi trả từ cache.
    if resolved_key in _recent_writes and resolved_key in _file_cache:
        _cache_invalidate(resolved_key)  # pop khỏi _file_cache nếu hash lệch (external edit)
    if resolved_key in _recent_writes and resolved_key in _file_cache:
        cached = _file_cache[resolved_key]
        cached_lines = cached["content"].splitlines()
        ctotal = len(cached_lines)
        start  = max(0, int(offset) - 1)
        end    = start + int(limit)
        sliced = cached_lines[start:end]
        out = (
            f"[policy] '{path}' đã được write/edit trong turn này — trả từ cache, "
            f"không đọc lại disk (content đã biết, xem rule re-read).\n"
            f"File: {p}\nVersion: {_content_hash(cached['content'])}\n"
            f"Lines {start+1}-{min(end, ctotal)} of {ctotal}\n"
            + "─" * 60 + "\n"
            + "\n".join(f"{start+1+i}\t{l}" for i, l in enumerate(sliced))
        )
        remaining = ctotal - end
        if remaining > 0:
            out += f"\n\n(+{remaining} more lines — call read with offset={end+1} if truly needed)"
        _record_file_observation(p, cached["content"])
        return _head_tail(out, _read_output_cap(int(limit)), label="read output")
    # Nếu vừa pop cache vì external edit, bỏ luôn khỏi _recent_writes để
    # nhánh đọc disk thật bên dưới chạy bình thường, không tự coi là "đã biết".
    _recent_writes.discard(resolved_key)

    try:
        size = p.stat().st_size
        if size > 50 * 1024 * 1024:
            return (f"[policy] File quá lớn ({size:,} bytes; tối đa 50 MiB cho read). "
                    "Dùng grep hoặc một tool chuyên dụng để thu hẹp dữ liệu.")
        raw_content = p.read_text(errors="replace")
        all_lines = raw_content.splitlines()
        total     = len(all_lines)

        # BUG FIX (đã verify bằng test thật, lịch sử): thứ tự cũ từng chạy
        # nhánh "large-file" TRƯỚC gate hard-block. Nhánh large-file kích
        # hoạt bất cứ khi nào offset==1 và limit>=total (đúng lúc model đọc
        # hết file lớn — chính là trường hợp gate được sinh ra để bắt), và nó
        # âm thầm ghi đè limit=80 TRƯỚC KHI gate kịp thấy giá trị limit thật
        # model truyền vào. Hệ quả: hard-block chết hẳn bất cứ khi nào
        # offset==1 — tức đường gọi tự nhiên nhất. Test xác nhận chỉ cần đổi
        # offset=1→2 (cùng limit, cùng file) là gate hoạt động lại đúng ngay,
        # chứng minh đây là bug thứ tự chứ không phải bug logic gate.
        # Fix: đánh giá gate TRƯỚC, trên limit GỐC model truyền vào (không
        # phụ thuộc offset/total) — đây là ý muốn tường minh của model, luôn
        # phải qua gate. Nhánh large-file chỉ còn xử lý phần CÒN LẠI: limit đã
        # qua gate (tức ≤700) nhưng vẫn đọc-hết-file (offset=1, limit>=total)
        # thì mới cảnh báo + cắt xuống threshold để tiết kiệm token.
        # (Update: verify-gate hỏi user khi limit>135 đã bị bỏ hoàn toàn —
        # gây phiền, không phù hợp luồng agent tự động. Giờ chỉ còn 1 ngưỡng
        # hard-block duy nhất = 700, không hỏi, không credit.)
        orig_limit = limit
        warn = ""

        # Hard block: AI tự ghi limit > READ_LIMIT_MAX (không còn verify-gate
        # hỏi user — đã bỏ theo yêu cầu, vì luồng hỏi/credit cũ gây phiền.
        # Giờ chỉ có 1 ngưỡng cứng duy nhất, vượt là từ chối thẳng, không hỏi lại.)
        # Large-file soft warning: nếu offset=1 và limit>=total (tức đọc hết
        # file lớn không cần thiết) → cắt xuống threshold để tiết kiệm token.
        _READ_LARGE_FILE_THRESHOLD = 80  # lines
        if (total > _READ_LARGE_FILE_THRESHOLD and int(offset) == 1
                and int(limit) >= total):
            warn += (
                f"[policy] File '{path}' có {total} dòng. "
                f"Đọc toàn bộ file lãng phí token.\n"
                f"Hãy dùng grep/view_symbol để tìm đúng vị trí trước, "
                f"rồi read với offset+limit hẹp.\n"
                f"Ví dụ: grep('tên_hàm') → read(path, offset=N-5, limit=30)\n"
                f"Hiển thị {_READ_LARGE_FILE_THRESHOLD} dòng đầu (tổng {total} dòng):\n"
            )
            limit = _READ_LARGE_FILE_THRESHOLD

        start     = max(0, int(offset) - 1)
        end       = start + int(limit)
        sliced    = all_lines[start:end]
        # Line numbers shown as annotation ONLY — do NOT include them in old_str for edit.
        # The exact file content is the part after the tab on each line.
        out = warn
        out += (f"File: {p}\nVersion: {_content_hash(raw_content)}\n"
                f"Lines {start+1}-{min(end, total)} of {total}\n")
        out += "NOTE: Line numbers below are display-only. For `edit` old_str, use ONLY the text after the line number, exactly as shown.\n"
        out += "─" * 60 + "\n"
        out += "\n".join(f"{start+1+i}\t{l}" for i, l in enumerate(sliced))
        remaining = total - end
        if remaining > 0:
            out += f"\n\n(+{remaining} more lines — call read with offset={end+1} or use grep to jump to the right section)"
        # Track the exact content version for edit/apply/extract safety checks
        _record_file_observation(p, raw_content)
        # Cache full content (không phải annotated output) để AI dùng lại
        if size <= 2 * 1024 * 1024:
            _cache_put(str(p), raw_content, _active_session_id())
        # Anchor map — AI biết structure file ngay, không cần grep lại turn sau
        amap = _anchor_map(all_lines, focus_line=start)
        if amap:
            out += f"\n\n{amap}"
        return _head_tail(out, _read_output_cap(orig_limit), label="read output")
    except Exception as e:
        return f"[error: {e}]"

def _check_sandbox_read(path: str) -> str | None:
    """
    Nếu project_dir đã được gán, chỉ cho phép đọc bên trong đó (hoặc cwd khi placeholder).
    Luôn chặn .fw_data và fw.py bất kể project_dir.
    Trả về error string nếu vi phạm, None nếu OK.
    """
    p = Path(path).expanduser().resolve()
    fw_data = (Path.cwd() / FW_DATA_NAME).resolve()
    try:
        p.relative_to(fw_data)
        return f"[not found: {path}]"   # Giả vờ không tồn tại, không lộ lý do
    except ValueError:
        pass

    # Chặn fw.py (entry loader) tuyệt đối — luôn ẩn, không lộ lý do
    fw_py = (Path.cwd() / "fw.py").resolve()
    if p == fw_py:
        return f"[not found: {path}]"

    if _project_dir is None:
        return None
    proj = _project_dir.resolve()
    try:
        p.relative_to(proj)
        return None  # OK — nằm trong sandbox
    except ValueError:
        return (f"[sandbox] Không được phép đọc '{path}'.\n"
                f"Chỉ được thao tác bên trong: {proj}")



def _edit_sanity_snap(lines: list[str], anchor_line: int) -> str:
    """3-point snapshot trả về sau edit: đầu / quanh edit / cuối.
    Đủ để AI verify structure còn nguyên mà không cần re-read.
    Giữ ngắn (~6 dòng tổng) để không tốn token."""
    total = len(lines)
    def _snip(start, end, label):
        chunk = lines[start:end]
        if not chunk:
            return ""
        joined = " | ".join(l.strip() for l in chunk if l.strip())[:80]
        return f"  {label}: {joined}"

    parts = []
    # Đầu file (dòng 1-2)
    head = _snip(0, 2, f"L1")
    if head:
        parts.append(head)
    # Quanh edit
    lo = max(0, anchor_line - 1)
    hi = min(total, anchor_line + 2)
    mid = _snip(lo, hi, f"L{lo+1}")
    if mid and mid != head:
        parts.append(mid)
    # Cuối file (2 dòng cuối)
    tail_start = max(0, total - 2)
    tail = _snip(tail_start, total, f"L{tail_start+1}")
    if tail and tail != mid:
        parts.append(tail)

    if not parts:
        return ""
    return "Snap: " + " · ".join(parts)

# ── History-compaction marker guard ──────────────────────────────────────────
# Khi lịch sử hội thoại bị nén (xem strip loop phía trên và trong
# 08_undo_dispatch.py), nội dung write/edit/patch cũ được thay bằng marker
# này. Nếu model từng "nhìn thấy" marker trong history và nhầm nó là nội
# dung thật cần ghi (đã xảy ra thực tế, gây SyntaxError khi marker bị ghi
# đè vào file .py), guard này chặn đứng thao tác ở tầng thực thi thay vì
# để lỗi lọt xuống file thật.
_HISTORY_COMPACTED_MARKER = "<<<HISTORY_COMPACTED_38f2a1_DO_NOT_COPY_THIS_MARKER_INTO_ANY_FILE>>>"

def _contains_compaction_marker(*texts) -> bool:
    return any(_HISTORY_COMPACTED_MARKER in (t or "") for t in texts)

_COMPACTION_MARKER_ERROR = (
    "[error] The content you provided is a history-compaction placeholder marker, "
    "not real file content. This means you copied it from an earlier (compacted) "
    "tool_call in the conversation history instead of writing actual content. "
    "Do NOT reuse that marker — write the real, full content/patch yourself."
)

def tool_write(path, content, conn=None, sid=None):
    if not isinstance(path, str) or not isinstance(content, str):
        return "[error: path and content must be strings]"
    if _contains_compaction_marker(content):
        return _COMPACTION_MARKER_ERROR
    # BUG FIX (đã verify bằng test thật): trước đây _resolve_to_sandbox(path)
    # chạy TRƯỚC check size-limit. _resolve_to_sandbox() gọi _ensure_project_dir()
    # bên trong, có side-effect VĨNH VIỄN: flip _project_dir_is_placeholder
    # True→False (khóa sandbox lại, mất quyền đọc project có sẵn ở cwd —
    # xem _check_sandbox_read/tool_read). Test tái hiện: gọi tool_write với
    # content 11MB (vượt limit 10MB, request chắc chắn KHÔNG ghi được file
    # nào) vẫn khiến sandbox bị enforce ngay, và tool_read một file project
    # có sẵn (đọc được trước đó) bị chặn ngay sau — dù không có gì được ghi.
    # Fix: check size-limit trên `content` trước, không cần biết path resolve
    # tới đâu. Chỉ resolve sandbox khi request có khả năng thực sự ghi file.
    _WRITE_SIZE_LIMIT = 10 * 1024 * 1024
    content_bytes = len(content.encode("utf-8", errors="replace"))
    if content_bytes > _WRITE_SIZE_LIMIT:
        return (f"[error] content too large ({content_bytes:,} bytes). "
                f"Limit is {_WRITE_SIZE_LIMIT:,} bytes. "
                f"If this is intentional, split into multiple files or use extract/apply_patch.")
    try:
        p = _resolve_to_sandbox(path)
    except ValueError as e:
        return f"[sandbox] {e}"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create ("x" mode) — loại race condition TOCTOU giữa check
        # p.exists() và write_text(): nếu file được tạo bởi tiến trình khác
        # (vd bash chạy song song) đúng lúc giữa 2 bước, "x" mode sẽ raise
        # FileExistsError thay vì âm thầm ghi đè.
        created = False
        try:
            with open(p, "x", encoding="utf-8") as f:
                created = True
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            return (f"[error] write only creates new files; '{p}' already exists. "
                    f"Use edit, multiedit, or apply_patch for existing files.")
        except Exception:
            # An I/O failure during an exclusive create can leave a partial
            # new file. Remove only the file this call successfully created;
            # never touch a pre-existing target that lost the race.
            if created:
                try:
                    p.unlink(missing_ok=True)
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"write failed ({write_error}); rollback failed: {rollback_error}"
                    ) from write_error
            raise
        before = None  # write chỉ chạy tới đây khi file chưa từng tồn tại
        # Track the exact version so subsequent edits do not false-alarm
        _record_file_observation(p, content)
        # Update cache ngay — AI không cần read lại file vừa tạo/ghi
        _cache_put(str(p), content, _active_session_id())
        _recent_writes.add(str(p.resolve()))  # block read-after-write
        if conn and sid:
            try:
                _undo_stack.append(snapshot_save(
                    conn, sid, str(p.resolve()), before, content,
                    before_mode=None, after_mode=p.stat().st_mode & 0o7777))
            except Exception as e:
                try:
                    p.unlink(missing_ok=True)
                    rollback_error = None
                except Exception as rollback_exc:
                    rollback_error = rollback_exc
                _file_cache.pop(str(p.resolve()), None)
                _forget_file_observation(p)
                _recent_writes.discard(str(p.resolve()))
                if rollback_error is not None:
                    return (f"[error] snapshot failed ({e}); write rollback failed: "
                            f"{rollback_error}")
                return f"[error] snapshot failed; write rolled back: {e}"
            _redo_stack.clear()
        redirected = f" (redirected from {path})" if str(p.resolve()) != str(Path(path).expanduser().resolve()) else ""
        # Inject anchor map — model biết structure ngay, không cần read/glob lại turn sau
        lines = content.splitlines()
        total = len(lines)
        amap = _anchor_map(lines)
        return (f"Written {content_bytes} bytes → {p} ({total} lines){redirected}"
                + (f"\n{amap}" if amap else ""))
    except UnicodeEncodeError as e:
        return f"[error: content contains characters that cannot be encoded as UTF-8: {e}]"
    except Exception as e:
        return f"[error: {e}]"


def tool_delete(path, conn=None, sid=None):
    """Xoá 1 file (không xoá thư mục). Khác tool_write/_resolve_to_sandbox:
    dùng _check_sandbox_read để TỪ CHỐI thẳng path ngoài sandbox thay vì
    redirect — với ghi (write) thì redirect vào đúng chỗ là hợp lý, nhưng
    với xoá thì redirect âm thầm có thể khiến model tưởng đã xoá đúng file
    trong khi thực ra xoá nhầm 1 file trùng tên khác trong sandbox.
    Ghi snapshot (before=nội_dung_cũ, after=None) để undo() phục hồi được,
    đối xứng với cách tool_write dùng before=None cho việc tạo mới.

    BUG FIX #1 (sandbox hở nếu delete là thao tác file đầu tiên trong
    session): trước đây hàm chỉ gọi _check_sandbox_read() (đọc flag), không
    bao giờ gọi _ensure_project_dir() (set flag is_placeholder=False) như
    tool_write/_resolve_to_sandbox làm. Nếu session chưa từng write, sandbox
    vẫn ở trạng thái placeholder ("chưa enforce"), nên delete có thể xoá bất
    kỳ file nào ngoài project_dir mà không bị chặn. Fix: nếu đang trong 1
    session thật (conn và sid có), gọi _ensure_project_dir() trước để trigger
    flip flag (bỏ qua giá trị trả về — không dùng để redirect path, giữ đúng
    triết lý "từ chối thẳng, không redirect" của tool này). Nếu không có
    conn/sid (gọi rời rạc, không qua session) thì giữ nguyên hành vi cũ,
    không đổi gì.

    BUG FIX #2 (mất file vĩnh viễn nếu snapshot_save lỗi): trước đây thứ tự
    là unlink() xong mới snapshot_save(), không bọc try/except quanh bước
    lưu snapshot. Nếu bước đó lỗi (DB lock, disk full, v.v.) → file đã mất,
    không undo được, exception bay thẳng ra ngoài. Fix: lưu snapshot TRƯỚC
    khi xoá thật, bọc trong try/except — nếu lỗi thì trả về thông báo lỗi,
    KHÔNG xoá file, giữ nguyên trạng thái an toàn. Chỉ khi snapshot lưu
    thành công (hoặc không có conn/sid — trường hợp không cần undo) mới gọi
    unlink(). snapshot_save() dùng 1 INSERT + commit() duy nhất (transaction
    đơn) nên nếu raise thì không có record nào bị ghi nửa chừng — không cần
    dọn dẹp gì thêm ở phía caller.
    """
    if not isinstance(path, str):
        return "[error: path must be a string]"
    # Establish the active project before resolving an absolute path. Without
    # this call the first delete in a session could run while the sandbox was
    # still in its permissive placeholder state and remove a file outside the
    # project. Unlike write, delete deliberately rejects (rather than
    # redirects) paths outside the project.
    if conn and sid:
        try:
            _ensure_project_dir(path)
        except Exception as e:
            return f"[sandbox] Không khởi tạo được project_dir; huỷ xoá: {e}"
    p = _resolve_read_path(path)
    err = _check_sandbox_read(str(p))
    if err:
        return err
    if not p.exists():
        return f"[not found: {path}]"
    if p.is_dir():
        return (f"[error] '{path}' là thư mục, tool này chỉ xoá file đơn lẻ "
                f"để tránh xoá nhầm hàng loạt. Xoá từng file bên trong nếu cần.")
    try:
        before = snapshot_encode_bytes(p.read_bytes())
    except Exception as e:
        return f"[error] Không đọc được file để lưu snapshot an toàn; huỷ xoá: {e}"

    resolved = str(p)
    snap = None
    if conn and sid:
        try:
            snap = snapshot_save(
                conn, sid, resolved, before, None,
                before_mode=p.stat().st_mode & 0o7777, after_mode=None)
        except Exception as e:
            return (f"[error] Không lưu được snapshot để undo, huỷ bỏ thao tác xoá "
                    f"(file '{path}' vẫn còn nguyên, chưa bị xoá): {e}")

    try:
        p.unlink()
    except Exception as e:
        if snap is not None:
            try:
                (conn or _project_dir_conn).execute(
                    "DELETE FROM file_snapshot WHERE id=?", (snap["id"],))
                (conn or _project_dir_conn).commit()
            except Exception as rollback_error:
                return (f"[error deleting {path}: {e}; snapshot rollback failed: "
                        f"{rollback_error}]")
        return f"[error deleting {path}: {e}]"

    _file_cache.pop(resolved, None)
    _forget_file_observation(p)
    _recent_writes.discard(resolved)
    if snap is not None:
        _undo_stack.append(snap)
        _redo_stack.clear()
    return f"Deleted {resolved}"

def tool_extract(src, start, end, dst, mode="move", conn=None, sid=None):
    """Lấy nguyên vẹn các dòng [start..end] (1-indexed, inclusive) từ src,
    append vào dst (tạo mới nếu chưa có). mode='move' (default) xoá vùng đó
    khỏi src; mode='copy' giữ src nguyên. Không qua model — tránh việc AI
    đọc rồi gõ lại nội dung khi tách/refactor file."""
    if not all(isinstance(v, str) for v in (src, dst)):
        return "[error: src and dst must be strings]"
    if mode not in ("move", "copy"):
        return "[error: mode must be 'move' or 'copy']"
    try:
        start, end = int(start), int(end)
    except (TypeError, ValueError):
        return "[error: start/end must be integers]"
    sp = _resolve_read_path(src)
    err = _check_sandbox_read(str(sp))
    if err:
        return err
    if not sp.exists():
        return f"[not found: {src}]"
    try:
        if sp.stat().st_size > 50 * 1024 * 1024:
            return "[policy] Source file quá lớn cho extract (>50 MiB); dùng công cụ streaming phù hợp."
    except OSError as e:
        return f"[error: cannot stat source: {e}]"
    try:
        dp = _resolve_to_sandbox(dst)
    except ValueError as e:
        return f"[sandbox] {e}"
    if sp.resolve() == dp.resolve():
        return "[error: src and dst must be different files]"
    dst_written = False
    src_written = False
    dst_snap = None
    src_snap = None
    dst_before = None
    src_before = None
    try:
        src_lines = sp.read_text().splitlines(keepends=True)
        src_before_mode = sp.stat().st_mode & 0o7777
        n = len(src_lines)
        if start < 1 or end < start or start > n:
            return f"[error: invalid range {start}-{end} for {sp} ({n} lines)]"
        end = min(end, n)
        chunk = src_lines[start-1:end]
        chunk_text = "".join(chunk)

        dp.parent.mkdir(parents=True, exist_ok=True)
        if dp.exists() and dp.stat().st_size > 50 * 1024 * 1024:
            return "[policy] Destination file quá lớn cho extract (>50 MiB); hãy xử lý/chia nhỏ trước."
        dst_before = dp.read_text() if dp.exists() else None
        dst_before_mode = (dp.stat().st_mode & 0o7777) if dp.exists() else None
        if dst_before is not None and dst_before and not dst_before.endswith("\n"):
            dst_after = dst_before + "\n" + chunk_text
        else:
            dst_after = (dst_before or "") + chunk_text

        # BUG FIX C: thiếu size-limit trên dst — cùng chuẩn với tool_write
        # (10MB), tránh dst phình vô hạn qua nhiều lần extract liên tiếp.
        _EXTRACT_SIZE_LIMIT = 10 * 1024 * 1024
        if len(dst_after.encode("utf-8", errors="replace")) > _EXTRACT_SIZE_LIMIT:
            return (f"[error] resulting {dp} would be too large "
                    f"({len(dst_after):,} chars). Limit is {_EXTRACT_SIZE_LIMIT:,} bytes.")

        # BUG FIX B (TOCTOU khi move — cùng loại bug đã fix ở tool_edit):
        # trước đây mode="move" ghi đè sp.write_text() không hề kiểm tra
        # file có bị sửa từ bên ngoài kể từ lần đọc gần nhất. Nếu process
        # khác sửa src giữa lúc agent đọc và lúc extract move, phần sửa đó
        # bị ghi đè mất trắng không cảnh báo. Check TRƯỚC khi ghi bất cứ gì
        # (kể cả dst) để giữ toàn bộ thao tác atomic-đúng-nghĩa khi fail.
        if mode == "move":
            resolved_src = str(sp.resolve())
            if not _file_matches_observation(sp, "".join(src_lines)):
                return (f"[error] File '{src}' differs from the version last read. "
                        "Read it again before extracting with mode='move'.")

        _atomic_write_text(dp, dst_after)
        dst_written = True
        _cache_put(str(dp), dst_after, _active_session_id())
        _record_file_observation(dp, dst_after)
        _recent_writes.add(str(dp.resolve()))
        # C11/C27 FIX: save snapshot cho dst để /undo restore được dst (cả copy lẫn move)
        extract_group = str(uuid.uuid4()) if conn and sid else None
        if conn and sid:
            try:
                dst_snap = snapshot_save(
                    conn, sid, str(dp.resolve()), dst_before, dst_after, extract_group,
                    before_mode=dst_before_mode,
                    after_mode=dp.stat().st_mode & 0o7777)
                _undo_stack.append(dst_snap)
            except Exception as e:
                if dst_before is None:
                    dp.unlink(missing_ok=True)
                else:
                    _atomic_write_text(dp, dst_before)
                if dst_before is None:
                    _file_cache.pop(str(dp.resolve()), None)
                    _forget_file_observation(dp)
                    _recent_writes.discard(str(dp.resolve()))
                else:
                    _cache_put(str(dp), dst_before, _active_session_id())
                    _record_file_observation(dp, dst_before)
                return f"[error] snapshot failed; extract rolled back: {e}"

        result = f"Extracted lines {start}-{end} of {sp} → {dp} ({len(chunk)} lines)"

        if mode == "move":
            src_before = "".join(src_lines)
            new_src_lines = src_lines[:start-1] + src_lines[end:]
            src_after = "".join(new_src_lines)
            _atomic_write_text(sp, src_after)
            src_written = True
            _record_file_observation(sp, src_after)
            _recent_writes.add(str(sp.resolve()))
            _cache_put(str(sp), src_after, _active_session_id())
            if conn and sid:
                try:
                    src_snap = snapshot_save(
                    conn, sid, str(sp.resolve()), src_before, src_after, extract_group,
                        before_mode=src_before_mode,
                        after_mode=sp.stat().st_mode & 0o7777)
                    _undo_stack.append(src_snap)
                except Exception as e:
                    # Roll back both files and remove the destination snapshot
                    # already created for this compound operation.
                    _atomic_write_text(sp, src_before)
                    if dst_before is None:
                        dp.unlink(missing_ok=True)
                    else:
                        _atomic_write_text(dp, dst_before)
                    _cache_put(str(sp), src_before, _active_session_id())
                    _record_file_observation(sp, src_before)
                    if dst_before is None:
                        _file_cache.pop(str(dp.resolve()), None)
                        _forget_file_observation(dp)
                        _recent_writes.discard(str(dp.resolve()))
                    else:
                        _cache_put(str(dp), dst_before, _active_session_id())
                        _record_file_observation(dp, dst_before)
                    if dst_snap is not None:
                        try:
                            _undo_stack.remove(dst_snap)
                            conn.execute("DELETE FROM file_snapshot WHERE id=?", (dst_snap["id"],))
                            conn.commit()
                        except Exception:
                            pass
                    return f"[error] snapshot failed; extract rolled back: {e}"
            result += f"\n[removed from {sp}, {len(new_src_lines)} lines remain]"

        if conn and sid:
            # Only invalidate redo after every file and every snapshot in the
            # compound operation has committed successfully.
            _redo_stack.clear()
        return result
    except Exception as e:
        # A destination write happens before a source write in move mode.
        # Any unexpected failure between those steps must restore both disk
        # state and snapshot metadata; otherwise extract can leave a partial
        # copy despite reporting an error.
        rollback_errors = []
        try:
            if src_written and src_before is not None:
                _atomic_write_text(sp, src_before)
        except Exception as rollback_error:
            rollback_errors.append(f"source rollback failed: {rollback_error}")
        try:
            if dst_written:
                if dst_before is None:
                    dp.unlink(missing_ok=True)
                else:
                    _atomic_write_text(dp, dst_before)
        except Exception as rollback_error:
            rollback_errors.append(f"destination rollback failed: {rollback_error}")
        if conn and sid:
            for snap in (src_snap, dst_snap):
                if snap is None:
                    continue
                try:
                    if snap in _undo_stack:
                        _undo_stack.remove(snap)
                    conn.execute("DELETE FROM file_snapshot WHERE id=?", (snap["id"],))
                    conn.commit()
                except Exception as rollback_error:
                    rollback_errors.append(f"snapshot rollback failed: {rollback_error}")
        rollback_states = []
        if src_written:
            rollback_states.append((sp, src_before))
        if dst_written:
            rollback_states.append((dp, dst_before))
        for path_obj, before_text in rollback_states:
            resolved_path = str(path_obj.resolve())
            if before_text is None:
                _file_cache.pop(resolved_path, None)
                _forget_file_observation(path_obj)
                _recent_writes.discard(resolved_path)
            else:
                _cache_put(str(path_obj), before_text, _active_session_id())
                _record_file_observation(path_obj, before_text)
                _recent_writes.discard(resolved_path)
        suffix = f"; {'; '.join(rollback_errors)}" if rollback_errors else ""
        return f"[error: extract failed and was rolled back: {e}{suffix}]"

def tool_edit(path, old_str, new_str, conn=None, sid=None):
    if not all(isinstance(v, str) for v in (path, old_str, new_str)):
        return "[error: path, old_str and new_str must be strings]"
    if _contains_compaction_marker(old_str, new_str):
        return _COMPACTION_MARKER_ERROR
    if len(old_str.encode("utf-8", errors="replace")) > 5 * 1024 * 1024 or len(new_str.encode("utf-8", errors="replace")) > 5 * 1024 * 1024:
        return "[error: old_str/new_str exceeds 5 MiB; use a narrower edit or apply_patch]"
    try:
        p = _resolve_to_sandbox(path, allow_redirect=False)
    except ValueError as e:
        return f"[sandbox] {e}"
    if not p.exists(): return f"[not found: {p}]"
    try:
        if p.stat().st_size > 50 * 1024 * 1024:
            return "[policy] File quá lớn cho edit (>50 MiB); dùng extract hoặc chia nhỏ thao tác."
        resolved = str(p.resolve())
        before_mode = p.stat().st_mode & 0o7777
        text  = p.read_text()
        if not _file_matches_observation(p, text):
            return (f"[error] File '{path}' differs from the version last read. "
                    "Use the read tool to reload it before editing.")
        if old_str == "":
            # str.count("") trả len(text)+1 (>=1 luôn), nên count==0/count>1
            # không bắt được case này. File rỗng đặc biệt nguy hiểm: count==1
            # lọt qua cả 2 check, khiến new_str bị ghi thẳng vào dù không có
            # gì để "replace". Chặn hẳn ở đây thay vì dựa vào side-effect của count.
            return ("[error: old_str cannot be empty] There is nothing to match against. "
                    "Use the `write` tool to create or populate a file instead of `edit`.")
        count = text.count(old_str)
        if count == 0:
            # C-fix: thông báo cụ thể hơn để model tự sửa nhanh, không đoán mù.
            snippet = old_str.strip()
            snippet = snippet[:80] + ("…" if len(snippet) > 80 else "")
            hint = (
                f"[error: old_str not found] The exact text you provided does not "
                f"appear in '{path}'.\n"
                f"old_str you sent (truncated): {snippet!r}\n"
                f"This usually means: (1) the file was rewritten (e.g. via `write`) since "
                f"your last `read`/`edit`, or (2) whitespace/line-ending differs from what "
                f"you remember. Re-`read` the file now to get its current exact content, "
                f"then retry `edit` with old_str copied verbatim from that fresh read — "
                f"do not reconstruct it from memory."
            )
            return hint
        if count > 1:  return f"[error: found {count} times — must be unique]"
        after = text.replace(old_str, new_str, 1)
        _atomic_write_text(p, after)
        # Record the exact content version after our own write so the next
        # edit/apply can distinguish it from an external change.
        _record_file_observation(p, after)
        # Update cache với content mới — AI thấy thay đổi ngay trong cache block
        _cache_put(str(p), after, _active_session_id())
        _recent_writes.add(str(p.resolve()))
        if conn and sid:
            try:
                _undo_stack.append(snapshot_save(
                    conn, sid, str(p.resolve()), text, after,
                    before_mode=before_mode,
                    after_mode=p.stat().st_mode & 0o7777))
            except Exception as e:
                try:
                    _snapshot_restore(p, text, before_mode)
                except Exception as rollback_error:
                    return (f"[error] snapshot failed ({e}); edit rollback failed: "
                            f"{rollback_error}")
                _cache_put(str(p), text, _active_session_id())
                _record_file_observation(p, text)
                _recent_writes.discard(str(p.resolve()))
                return f"[error] snapshot failed; edit rolled back: {e}"
            _redo_stack.clear()
        # Trả về context snippet quanh vùng thay đổi — AI không cần read lại để verify
        lines_before = text.splitlines()
        lines_after  = after.splitlines()
        total = len(lines_after)
        # Tìm dòng đầu tiên khác nhau giữa before/after → anchor chính xác, không bị false match
        anchor_line = 0
        for i, (a, b) in enumerate(zip(lines_before, lines_after)):
            if a != b:
                anchor_line = i
                break
        else:
            # Không tìm thấy qua zip (new_str thêm dòng ở cuối, hoặc xóa dòng)
            anchor_line = min(len(lines_before), len(lines_after)) - 1
        new_lines = new_str.splitlines()
        ctx_start = max(0, anchor_line - 2)
        ctx_end   = min(total, anchor_line + max(len(new_lines), 1) + 2)
        snippet = "\n".join(f"{ctx_start+1+i}: {l}" for i, l in enumerate(lines_after[ctx_start:ctx_end]))
        amap = _anchor_map(lines_after, focus_line=anchor_line)
        snap = _edit_sanity_snap(lines_after, anchor_line)
        return (f"Edited {path} ({total} lines total)\n{snippet}"
                + (f"\n{snap}" if snap else "")
                + (f"\n\n{amap}" if amap else ""))
    except Exception as e:
        return f"[error: {e}]"

def tool_multiedit(path, edits, conn=None, sid=None):
    """Apply multiple str-replace edits to a single file, all-or-nothing.

    Truoc day ham nay goi tool_edit() tuan tu - moi edit tu ghi xuong dia
    ngay lap tuc. Neu edit thu N (N>1) fail, cac edit 1..N-1 da ghi that
    xuong file roi va KHONG duoc rollback, khien file ket o trang thai nua
    voi khong giong ban goc cung khong giong ket qua mong muon - trong khi
    thong bao loi khien model tuong "chua co gi thay doi". Ngoai ra moi edit
    con tu day 1 snapshot rieng vao _undo_stack, nen 1 lan goi multiedit tao
    ra N undo-step roi rac thay vi 1 - undo() mot lan chi lui duoc buoc cuoi.
    Fix: ap toan bo edit len mot buffer trong RAM truoc; chi khi TAT CA edit
    hop le moi ghi xuong dia mot lan va tao dung mot undo-snapshot duy nhat.
    """
    if not isinstance(path, str):
        return "[error: path must be a string]"
    if not isinstance(edits, list) or len(edits) > 50:
        return "[error: edits must be a list of at most 50 items]"
    if not edits:
        return "[error: no edits provided]"
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            return f"[error: edits[{i}] must be an object with old_str and new_str]"
        old_str, new_str = edit.get("old_str"), edit.get("new_str")
        if not isinstance(old_str, str) or not isinstance(new_str, str):
            return f"[error: edits[{i}].old_str and new_str must be strings]"
        if len(old_str.encode("utf-8", errors="replace")) > 5 * 1024 * 1024 \
                or len(new_str.encode("utf-8", errors="replace")) > 5 * 1024 * 1024:
            return f"[error: edits[{i}] old_str/new_str exceeds 5 MiB]"
    if _contains_compaction_marker(*[
        v for e in edits for v in (e.get("old_str"), e.get("new_str"))
    ]):
        return _COMPACTION_MARKER_ERROR
    if sum(len(e["old_str"].encode("utf-8", errors="replace"))
           + len(e["new_str"].encode("utf-8", errors="replace")) for e in edits) > 10 * 1024 * 1024:
        return "[error: combined edit content exceeds 10 MiB]"
    try:
        p = _resolve_to_sandbox(path, allow_redirect=False)
    except ValueError as e:
        return f"[sandbox] {e}"
    if not p.exists(): return f"[not found: {p}]"
    try:
        resolved = str(p.resolve())
        if p.stat().st_size > 50 * 1024 * 1024:
            return "[policy] File quá lớn cho multiedit (>50 MiB); dùng extract hoặc chia nhỏ thao tác."
        before_mode = p.stat().st_mode & 0o7777
        before = p.read_text()
        if not _file_matches_observation(p, before):
            return (f"[error] File '{path}' differs from the version last read. "
                    "Use the read tool to reload it before editing.")
        buf = before
        results = []
        for i, edit in enumerate(edits):
            old_str = edit.get("old_str", "")
            new_str = edit.get("new_str", "")
            if old_str == "":
                results.append(f"[edit {i+1}] [error: old_str cannot be empty]")
                results.append(f"[multiedit aborted at edit {i+1} - no changes written]")
                return "\n".join(results)
            count = buf.count(old_str)
            if count == 0:
                snippet = old_str.strip()
                snippet = snippet[:80] + ("..." if len(snippet) > 80 else "")
                results.append(
                    f"[edit {i+1}] [error: old_str not found] Text not found "
                    f"(searching against the file state *after* the previous "
                    f"edits in this same multiedit call, if any).\n"
                    f"old_str you sent (truncated): {snippet!r}"
                )
                results.append(f"[multiedit aborted at edit {i+1} - no changes written]")
                return "\n".join(results)
            if count > 1:
                results.append(f"[edit {i+1}] [error: found {count} times - must be unique]")
                results.append(f"[multiedit aborted at edit {i+1} - no changes written]")
                return "\n".join(results)
            buf = buf.replace(old_str, new_str, 1)
            results.append(f"[edit {i+1}] ok")

        # Tat ca edit hop le - commit mot lan duy nhat.
        after = buf
        _atomic_write_text(p, after)
        _record_file_observation(p, after)
        _recent_writes.add(resolved)
        _cache_put(str(p), after, _active_session_id())
        if conn and sid:
            try:
                _undo_stack.append(snapshot_save(
                    conn, sid, resolved, before, after,
                    before_mode=before_mode,
                    after_mode=p.stat().st_mode & 0o7777))
            except Exception as e:
                try:
                    _snapshot_restore(p, before, before_mode)
                except Exception as rollback_error:
                    return (f"[error] snapshot failed ({e}); multiedit rollback failed: "
                            f"{rollback_error}")
                _cache_put(str(p), before, _active_session_id())
                _record_file_observation(p, before)
                _recent_writes.discard(resolved)
                return f"[error] snapshot failed; multiedit rolled back: {e}"
            _redo_stack.clear()

        final_lines = after.splitlines()
        total = len(final_lines)
        results.append(f"Applied {len(edits)} edits to {path} ({total} lines total)")
        snap = _edit_sanity_snap(final_lines, max(0, total // 2))
        if snap:
            results.append(snap)
        return "\n".join(results)
    except Exception as e:
        return f"[error: {e}]"


def _anchor_map(lines: list[str], focus_line: int | None = None) -> str:
    """Build a compact anchor map: line numbers of def/class/function/heading.

    focus_line: 0-based line index of the edit area. If provided, returns up to
    12 anchors centered around that area (6 before + 6 after) rather than just
    the first 12 anchors of the file.
    """
    _pat = re.compile(
        r"^\s*("
        r"def |async def |class |function\s|function\(|"           # Python/JS functions
        r"export |export default |"                                  # JS/TS exports
        r"const \w+\s*=\s*\(|const \w+\s*=\s*async|"                 # arrow function consts
        r"interface |type \w+\s*=|enum |"                             # TS types
        r"#\s*##==\s*\w|##==\s*\w|"                                  # section markers ##== NAME ==## (with or without leading #)
        r"# |## |### |#### |"                                         # markdown / comments
        r"@app\.|@\w+|"                                               # decorators (Flask, etc.)
        r"<(h[1-6]|section|nav|header|footer|main|article|aside|form|table)\b|" # HTML structural tags
        r"@media|@keyframes|@font-face|"                              # CSS at-rules
        r"(?!if |for |while |switch |else|catch|return |function)[.#a-zA-Z][\w\-\.\#\s:,>+~\[\]=\"']*\{\s*$|"  # generic CSS selectors
        r"\w+:\s*$|"                                                  # YAML/JSON-ish top-level keys
        r"(public|private|protected|static)\s+\w|"                   # Java/C#/PHP methods
        r"fn \w|async fn \w|impl \w|pub fn \w|pub async fn \w|"      # Rust
        r"func \w|"                                                    # Go
        r"(void|int|char|bool|string|uint|float|double|size_t)\s+\w+\s*\("  # C/C++
        r")"
    )
    # Collect ALL matching anchor line numbers (1-based), tagged with a type
    def _classify(s: str) -> str:
        t = s.lstrip()
        if t.startswith(("def ", "async def ")): return "fn"
        if t.startswith("class "): return "class"
        if t.startswith(("function", "export default", "export ")): return "fn"
        if t.startswith(("const ",)) and "=>" in t: return "fn"
        if t.startswith(("interface ", "type ", "enum ")): return "type"
        if t.startswith(("fn ", "async fn ", "pub fn ", "pub async fn ")): return "fn"
        if t.startswith("impl "): return "class"
        if t.startswith("func "): return "fn"
        if any(t.startswith(k) for k in ("void ", "int ", "char ", "bool ", "string ", "uint ", "float ", "double ", "size_t ")): return "fn"
        if t.startswith(("public ", "private ", "protected ", "static ")): return "method"
        if t.startswith(("@media", "@keyframes", "@font-face")): return "css"
        if t.startswith(("@",)): return "deco"
        if t.startswith("##==") or "##==" in t[:6]: return "sec"
        if t.startswith("#"): return "md"
        if t.startswith("<"): return "html"
        if t.startswith((".", "#")) or t.rstrip().endswith("{"): return "css"
        if t.rstrip().endswith(":"): return "key"
        return "·"

    all_anchors = []
    for i, line in enumerate(lines, 1):
        if _pat.match(line):
            all_anchors.append((i, _classify(line), line.strip()[:65]))

    if not all_anchors:
        return ""

    if focus_line is None:
        # Legacy behaviour: first 12
        selected = all_anchors[:12]
    else:
        focus_1based = focus_line + 1  # convert to 1-based
        # Find closest anchor index to focus_line
        closest = min(range(len(all_anchors)), key=lambda k: abs(all_anchors[k][0] - focus_1based))
        lo = max(0, closest - 6)
        hi = min(len(all_anchors), closest + 6)
        selected = all_anchors[lo:hi]

    found = [f"  L{lineno:<5} [{kind:<6}] {text}" for lineno, kind, text in selected]
    return "Anchors:\n" + "\n".join(found)
