def tool_set_tools(tools: list) -> str:
    global _active_tools
    valid   = [t for t in tools if t in ALL_TOOL_NAMES]
    invalid = [t for t in tools if t not in ALL_TOOL_NAMES]
    # Luôn giữ set_tools để AI có thể thay đổi lại
    if "set_tools" not in valid:
        valid.append("set_tools")
    _active_tools = set(valid)
    active_label = ", ".join(sorted(_active_tools))
    msg = f"Tool focus set: {active_label} (full tool schema remains available)"
    if invalid:
        msg += f" (unknown: {', '.join(invalid)})"
    return msg

def get_active_tools() -> list:
    """Full tool schema is kept stable to preserve prompt-cache reuse."""
    return TOOLS

# ════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ════════════════════════════════════════════════════════════════════════════


# Các pattern bash nguy hiểm có thể escape sandbox
_BASH_DENY_PATTERNS = [
    r"\bcd\s+/",           # cd /... (absolute)
    r"\bcd\s+\.\.",        # cd ..
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
]
_BASH_DENY_RE = re.compile("|".join(_BASH_DENY_PATTERNS))


# ── Bash safety gates ───────────────────────────────────────────────────────
# Bash is arbitrary code execution, not a filesystem sandbox. Build mode asks
# for explicit permission; plan mode denies it completely.
# Có 2 lớp permission độc lập:
#   Lớp 1 — _check_permission() trong 08_undo_dispatch.py: hỏi "Allow? [y/N/a]"
#            /perm bash allow chỉ ảnh hưởng lớp này (bỏ câu hỏi confirm).
#   Lớp 2 — allowlist dưới đây (_BASH_ALLOW_RE): chặn
#            lệnh không nằm trong danh sách (git/pytest/python/node/npm/make).
#            /perm bash allow KHÔNG tắt lớp này — 2 lớp hoàn toàn độc lập.
#   FIX (bug #1): trước đây allowlist chỉ check LỆNH ĐẦU TIÊN của session —
#            sau khi 1 lệnh khớp allowlist chạy qua, cờ "_BASH_CONFIRMED" được
#            set True vĩnh viễn và mọi lệnh sau đó (kể cả "rm -rf foo") bỏ qua
#            hoàn toàn allowlist. Giờ allowlist được check ở MỌI lệnh — không
#            còn cờ "đã confirm" nào tắt gate này nữa.
_BASH_ALLOWLIST = [
    r"^git\b",
    r"^pytest\b",
    r"^python(3)?\b",
    r"^node\b",
    r"^npm\b",
    r"^pnpm\b",
    r"^yarn\b",
    r"^make\b",
]
_BASH_ALLOW_RE = re.compile("|".join(_BASH_ALLOWLIST), re.IGNORECASE)

# Pattern chặn file inspection qua bash — AI phải dùng read/glob/grep thay thế
# head/tail chỉ block khi đứng đầu lệnh (không phải sau pipe)
# FIX (bug #2): trước đây các pattern chỉ bắt khi cat/less/head/tail/find
#            đứng ngay sau ^ / && / ; — dễ bypass bằng subshell "(cat f)"
#            hoặc "bash -c 'cat f'" / "sh -c 'cat f'". Giờ thêm "(" làm
#            boundary hợp lệ, và chặn riêng cú pháp "bash -c"/"sh -c"/"zsh -c"
#            vì nội dung trong dấu quote không thể parse an toàn bằng regex.
_BASH_INSPECT_PATTERNS = [
    r"(?:^|&&|;|\()\s*cat\s+\S",           # cat <file> hoặc (cat <file>)
    r"(?:^|&&|;|\()\s*less\s+\S",          # less <file> hoặc (less <file>)
    r"(?:^|&&|;|\()\s*head\s+",            # head ... ở đầu lệnh / trong subshell
    r"(?:^|&&|;|\()\s*tail\s+",            # tail ... ở đầu lệnh / trong subshell
    r"(?:^|&&|;|\||\()\s*ls\s+-[a-zA-Z]*R",# ls -R, ls -lR ở bất kỳ đâu
    r"(?:^|&&|;|\()\s*find\s+[./]",        # find . / find ./dir
    r"\b(?:bash|sh|zsh)\s+-c\b",           # bash -c "..." / sh -c "..." — chặn
                                            # toàn bộ vì nội dung bên trong quote
                                            # không kiểm tra an toàn bằng regex.
]
_BASH_INSPECT_RE = re.compile("|".join(_BASH_INSPECT_PATTERNS))

# ── Nhánh riêng: "serve:" — chạy 1 process SỐNG MÃI (preview dev server) ────
# Lý do cần tách hẳn khỏi logic bash thường (không chung code path, không
# đụng allowlist/deny/timeout cũ ở dưới): subprocess.run(...) mặc định CHỜ
# process kết thúc. Với 1 lệnh cố ý chạy mãi mãi (http.server, node listen,
# npm run dev...), nó KHÔNG BAO GIỜ tự thoát -- tool_bash cũ luôn timeout sau
# N giây, và tệ hơn: shell=True tạo ra shell (con) -> lệnh thật (cháu), khi
# TimeoutExpired chỉ kill được shell (con), process thật (cháu) SỐNG SÓT làm
# zombie giữ nguyên cổng mãi mãi -- xác nhận bằng thực nghiệm (pgrep vẫn thấy
# process sau khi TimeoutExpired). Mỗi lần agent thử lại -> thêm 1 zombie mới,
# không dọn cái cũ, cổng dần bị chiếm hết không rõ lý do.
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
        except Exception:
            pass  # dọn best-effort, không để lỗi kill làm hỏng luồng start-mới
    return old_cmd

# Bắt số port từ CUỐI lệnh serve (vd "python3 -m http.server 8080",
# "node server.js 3000", "vite --port 5173") -- chỉ cần số đứng riêng lẻ
# (ranh giới \b) để không bắt nhầm số bên trong path/tên file. Không bắt
# được -> bỏ qua bước check port (an toàn, không đoán bừa), rơi về hành vi
# cũ y hệt trước khi có fix này.
_SERVE_PORT_RE = re.compile(r"\b(\d{2,5})\b")

def _serve_find_port(inner_command: str) -> int | None:
    """Đoán port từ lệnh serve, ưu tiên số đứng SAU CÙNG (thường là port thật,
    vd "http.server 8080" hay "--port 5173") -- best-effort, chỉ dùng để check
    port bận trước khi Popen, không dùng cho auto-detect entry file (đã có
    _HTTP_SERVER_RE riêng, chặt chẽ hơn, cho việc đó)."""
    nums = _SERVE_PORT_RE.findall(inner_command)
    if not nums:
        return None
    port = int(nums[-1])
    if 1 <= port <= 65535:
        return port
    return None

def _serve_kill_port_owner(run_cwd: str, port: int) -> str | None:
    """Nếu có process NGOÀI hệ thống 'serve:' (không phải _serve_procs đang
    track) đang chiếm sẵn `port` -- ví dụ 1 lệnh `node -e ...`/server cũ user
    tự chạy tay từ trước, hoặc zombie sống sót qua 1 lần app bị kill cứng --
    dò và kill nó trước khi Popen lệnh serve mới. Lý do cần bước này: nếu
    không kill, lệnh serve mới có thể bind FAIL (EADDRINUSE, phát hiện được
    qua nhánh 'Process thoát ngay' bên dưới) HOẶC tệ hơn, tuỳ hệ điều hành/
    tuỳ cấu hình SO_REUSEPORT, request có thể vẫn lọt vào process CŨ thay vì
    process MỚI -- kết quả là server tưởng đã chạy nhưng client luôn thấy
    404/nội dung cũ, không có cách nào phát hiện qua exit_code vì process
    mới của TA vẫn sống bình thường (bug 404 thực tế đã xảy ra với Termux +
    'node -e' chiếm port 8080 từ trước, xác nhận qua ps aux + curl).
    Trả về mô tả process đã kill (để log/báo), hoặc None nếu port đang rảnh
    hoặc không dò được gì (best-effort, không có quyền root/netlink trên
    Termux nên KHÔNG dùng ss/netstat/lsof -- quét /proc trực tiếp thay thế).
    """
    import socket as _sock
    # CHẶN AN TOÀN: không bao giờ kill nếu port này chính là port của web UI
    # server chính (12_web.py, /web mode) -- đây là server phục vụ CHÍNH cái
    # web UI mà agent đang chạy trong đó, kill nhầm nó = tự cắt kết nối của
    # chính mình. web_server_addr() chỉ tồn tại nếu module 12_web.py đã được
    # load (dùng globals().get() để không NameError ở nhánh CLI thuần, nơi
    # /web chưa từng được bật -- symbol có thể chưa tồn tại trong namespace
    # chung tại thời điểm này). Chỉ áp dụng đúng khi web server ĐANG chạy
    # (web_server_addr() trả None nếu chưa start) -- nhánh CLI không bị ảnh
    # hưởng gì, hành vi kill-port vẫn hoạt động bình thường như cũ.
    _addr_fn = globals().get("web_server_addr")
    if _addr_fn is not None:
        try:
            _addr = _addr_fn()
        except Exception:
            _addr = None
        if _addr is not None and _addr[1] == port:
            _serve_log(run_cwd, f"Port {port} trùng port web UI server đang chạy "
                                 f"({_addr}) -- BỎ QUA kill để không tự cắt kết nối "
                                 f"chính mình.")
            return None
    # 1) Test nhanh: port có đang bận không? Bind thử lên 127.0.0.1 -- nếu
    # thành công nghĩa là port đang RẢNH, không cần làm gì thêm.
    s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return None  # port rảnh -- không có gì để kill
    except OSError:
        s.close()  # port đang bận -- tiếp tục dò process nào giữ nó
    # 2) Quét /proc để tìm pid nào có socket inode khớp port đang LISTEN.
    # Không cần root: đọc /proc/net/tcp (địa chỉ hex, port ở dạng hex sau
    # dấu ":") để lấy inode, rồi map inode -> pid qua /proc/<pid>/fd/*.
    try:
        port_hex = format(port, "04X")
        target_inodes = set()
        for tcp_file in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(tcp_file) as f:
                    next(f)  # bỏ header
                    for line in f:
                        parts = line.split()
                        local_addr, state, inode = parts[1], parts[3], parts[9]
                        if local_addr.split(":")[1] == port_hex and state == "0A":  # 0A = LISTEN
                            target_inodes.add(inode)
            except FileNotFoundError:
                pass
        candidate_pid = None
        candidate_cmd = None
        if target_inodes:
            # Đường chính: map inode -> pid qua /proc/<pid>/fd/* (chính xác
            # tuyệt đối khi network namespace không bị ảo hoá lệch, đúng
            # trường hợp Termux/Android thật).
            for pid_dir in Path("/proc").glob("[0-9]*"):
                pid = pid_dir.name
                fd_dir = pid_dir / "fd"
                try:
                    matched = False
                    for fd in fd_dir.iterdir():
                        try:
                            link = os.readlink(fd)
                        except OSError:
                            continue
                        if link.startswith("socket:[") and link[8:-1] in target_inodes:
                            matched = True
                            break
                    if matched:
                        candidate_pid = pid
                        break
                except Exception:
                    continue  # 1 pid lỗi đọc /proc (race condition, permission...) -- thử pid khác
        if candidate_pid is None:
            # Fallback: 1 vài môi trường (container ảo hoá network namespace
            # khác lạ) khiến inode ở /proc/net/tcp không khớp trực tiếp với
            # /proc/<pid>/fd dù cùng 1 process thật -- xác nhận qua thực
            # nghiệm. Dò thêm bằng cách tìm process có cmdline chứa đúng số
            # port này VÀ đang có ít nhất 1 fd loại socket đang mở -- kém
            # chính xác hơn (có thể trùng số ngẫu nhiên trong cmdline), nên
            # CHỈ dùng khi đường chính thất bại, và chỉ kill nếu tìm được
            # ĐÚNG 1 ứng viên duy nhất (mơ hồ -> bỏ qua, không đoán bừa).
            port_str = str(port)
            found = []
            for pid_dir in Path("/proc").glob("[0-9]*"):
                pid = pid_dir.name
                try:
                    cmdline = (pid_dir / "cmdline").read_bytes().decode(errors="replace").replace("\x00", " ").strip()
                except OSError:
                    continue
                if port_str not in cmdline:
                    continue
                try:
                    has_socket = any(
                        os.readlink(fd).startswith("socket:[")
                        for fd in (pid_dir / "fd").iterdir()
                        if True
                    )
                except Exception:
                    has_socket = False
                if has_socket:
                    found.append((pid, cmdline))
            if len(found) == 1:
                candidate_pid, candidate_cmd = found[0]
        if candidate_pid is None:
            return None  # không dò ra được (0 hoặc >1 ứng viên mơ hồ) -- bỏ qua an toàn
        # CHẶN AN TOÀN THỨ 2 (tự vệ tuyệt đối): không bao giờ kill chính pid
        # process app đang chạy (os.getpid()), pid cha của nó (os.getppid(),
        # vd tiến trình shell/Termux bao ngoài), hay bất kỳ pid nào đang được
        # CHÍNH hệ thống serve: track trong _serve_procs (những pid đó đã có
        # đường dọn riêng qua _serve_kill_existing/killpg ở trên rồi -- nếu
        # lọt tới đây nghĩa là có sai lệch dò tìm, an toàn nhất là bỏ qua
        # thay vì kill nhầm process CỦA CHÍNH HỆ THỐNG).
        _protected_pids = {str(os.getpid()), str(os.getppid())}
        for _entry in _serve_procs.values():
            _protected_pids.add(str(_entry["proc"].pid))
        if candidate_pid in _protected_pids:
            _serve_log(run_cwd, f"Dò ra pid={candidate_pid} giữ port {port} nhưng đây là "
                                 f"process được bảo vệ (chính app hoặc server serve: đang "
                                 f"track) -- BỎ QUA kill để tránh tự hại chính mình.")
            return None
        if candidate_cmd is None:
            try:
                candidate_cmd = (Path("/proc") / candidate_pid / "cmdline").read_bytes().decode(errors="replace").replace("\x00", " ").strip()
            except OSError:
                candidate_cmd = "?"
        try:
            os.kill(int(candidate_pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError) as e:
            _serve_log(run_cwd, f"Dò thấy pid={candidate_pid} ({candidate_cmd}) giữ port {port} "
                                f"nhưng KHÔNG kill được: {e!r}")
            return None
        _serve_log(run_cwd, f"Port {port} đang bị pid={candidate_pid} ({candidate_cmd}) chiếm "
                             f"(ngoài hệ thống serve:) -- đã kill để nhường chỗ.")
        return f"pid={candidate_pid} ({candidate_cmd})"
    except Exception as e:
        _serve_log(run_cwd, f"LỖI dò process giữ port {port}: {e!r}")
    return None

def tool_bash_serve(inner_command: str) -> str:
    """Nhánh 'serve:' của tool_bash -- xem comment khối phía trên. Tách hàm
    riêng để code path hoàn toàn độc lập, dễ đọc, không lẫn vào nhánh bash
    thường (không share biến/state nào ngoài _project_dir đọc-only)."""
    inner_command = inner_command.strip()
    if not inner_command:
        return "[serve] Thiếu lệnh sau 'serve:'. Cú pháp: serve: <lệnh chạy server>."
    key = _serve_key()
    old_cmd = _serve_kill_existing(key)
    if old_cmd:
        time.sleep(0.15)  # đệm nhỏ: os.killpg gửi SIGTERM cho cả process group,
        # nhưng proc.wait() ở _serve_kill_existing chỉ đảm bảo process CHA (shell,
        # do shell=True) đã chết -- process CON thật (vd http.server) nhận SIGTERM
        # cùng lúc nhưng có thể cần thêm chút thời gian để tự thoát (khác SIGKILL
        # chết ngay tức khắc). Không có đệm này, bước check port ngay sau đây có
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
    guessed_port = _serve_find_port(inner_command)
    killed_owner = None
    if guessed_port is not None:
        killed_owner = _serve_kill_port_owner(run_cwd, guessed_port)
        if killed_owner:
            time.sleep(0.2)  # nhường chút thời gian để OS giải phóng hẳn port
            # sau SIGKILL trước khi ta bind lại -- tránh race hiếm gặp EADDRINUSE
            # dù process đã chết (TIME_WAIT thường không áp dụng cho SIGKILL
            # tức thời, nhưng thêm 1 khoảng nhỏ vẫn an toàn hơn không có gì).
    try:
        proc = subprocess.Popen(
            inner_command, shell=True, cwd=run_cwd,
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
    killed_note = f" Đã phát hiện và dọn process lạ giữ port trước đó: {killed_owner}.\n" if killed_owner else ""
    base_msg = (
        f"[serve] Đang chạy nền, pid={proc.pid}{replaced_note}.\n"
        f"Lệnh: {inner_command}\n"
        f"Thư mục: {run_cwd}\n"
        f"{killed_note}"
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

def tool_bash(command, timeout=30):
    # Nhánh riêng "serve: ..." -- rẽ NGAY ĐẦU, trước mọi gate/logic bash
    # thường bên dưới, vì đây là 1 cơ chế khác hẳn (Popen nền, không chờ,
    # không timeout). Không dùng "serve:" -> rơi xuống logic gốc, không đổi
    # gì cho các lệnh khác.
    m = _SERVE_PREFIX_RE.match(command)
    if m:
        return tool_bash_serve(command[m.end():])

    # Chặn file inspection qua bash — AI phải dùng read/glob/grep thay thế
    if _BASH_INSPECT_RE.search(command):
        return (
            "[policy] Không được dùng bash để đọc/liệt kê file.\n"
            "Dùng các tool chuyên dụng thay thế:\n"
            "  • cat / head / tail / less  → read(path, offset, limit)\n"
            "  • ls -R / find .            → glob(pattern) hoặc read(dir)\n"
            "  • bash -c / sh -c           → không hỗ trợ, dùng tool trực tiếp\n"
            "Lý do: bash file inspection lãng phí token, phá cache context,\n"
            "và subshell/`-c` không kiểm tra an toàn được bằng policy này."
        )



    # ── Allowlist gate (minimal) — áp dụng cho MỌI lệnh, không chỉ lệnh đầu ──
    if not _BASH_ALLOW_RE.search(command.strip()):
        return (
            "[policy] bash command blocked by allowlist.\n"
            "Hãy dùng lệnh trong allowlist (git/pytest/python/node/npm/make) hoặc\n"
            "đổi strategy (tools read/write/edit/apply_patch)."
        )
    if _project_dir is not None:
        proj = _project_dir.resolve()

        # Block obvious destructive commands as defense in depth. This is not
        # a security boundary: an allowed interpreter can access host files.
        if _BASH_DENY_RE.search(command):
            return (f"[policy] Lệnh nguy hiểm bị chặn.\n"
                    f"Thư mục chạy dự kiến: {proj}\n"
                    f"Lệnh bị từ chối: {command[:200]}")

        # Chạy trong project_dir, không phải cwd tuỳ tiện
        run_cwd = str(proj)
        # Inject cd để chắc chắn shell bắt đầu đúng chỗ
        wrapped = f"cd {shlex.quote(run_cwd)} && {command}"
    else:
        run_cwd = os.getcwd()
        wrapped = command

    started = time.time()
    try:
        r = subprocess.run(wrapped, shell=True, capture_output=True,
                           text=True, timeout=int(timeout), cwd=run_cwd)
        elapsed = time.time() - started
        return _format_bash_result(command, r.returncode, r.stdout, r.stderr,
                                   elapsed, timed_out=False, run_cwd=run_cwd)
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - started
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        if isinstance(stdout, bytes): stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes): stderr = stderr.decode("utf-8", errors="replace")
        return _format_bash_result(command, 124, stdout, stderr, elapsed,
                                   timed_out=True, timeout=timeout, run_cwd=run_cwd)
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
TOOL_OUTPUT_MAX_CHARS   = 12_000   # ~3k tokens — what model sees live
TOOL_HISTORY_MAX_CHARS  = 3_000    # ~500 tokens — what stays in context forever
TOOL_KEEP_FULL_TURNS    = 4        # giữ tool_result đầy đủ cho N turn gần nhất
READ_DEFAULT_LIMIT      = 80       # lines, down from 200

def _head_tail(text: str, max_chars: int, label="tool output") -> str:
    """Keep head + tail, drop middle. Model knows exactly what was cut."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    head = text[:half]
    tail = text[-half:]
    cut  = len(text) - max_chars
    return f"{head}\n\n... [{cut:,} chars omitted from middle of {label}] ...\n\n{tail}"

def _prune_tool_results(messages: list) -> list:
    """
    Giảm token tool_result trong context:
    1. Stub các tool_result cũ hơn TOOL_KEEP_FULL_TURNS
    2. Dedup read/glob/grep: nếu cùng file bị read nhiều lần,
       chỉ giữ lần gần nhất đầy đủ, các lần cũ hơn → stub
    """
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
    old_groups = groups[:-TOOL_KEEP_FULL_TURNS] if len(groups) > TOOL_KEEP_FULL_TURNS else []
    stub_indices = set()
    for start, end in old_groups:
        for idx in range(start, end + 1):
            stub_indices.add(idx)

    # ── Bước 2: dedup read/glob/grep theo file path ───────────────────────────
    # Map tool_call_id → tool_name cho các assistant messages
    # FIX (bug #4): tool "glob" dùng tham số "pattern"/"cwd", KHÔNG có "path"
    # (xem schema trong 05_session_db.py). Code cũ chỉ đọc args.get("path", "")
    # nên với "glob" key dedup luôn là "" → "not path" = True → toàn bộ kết quả
    # glob bị skip khỏi dedup, dù "glob" có mặt trong DEDUPABLE bên dưới (dead
    # code). Giờ xây dựng key riêng cho từng tool: glob dùng "cwd|pattern".
    tc_id_to_name: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                name = tc.get("function", {}).get("name", "")
                args_raw = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}
                if name == "glob":
                    # glob không có "path" — dùng cwd+pattern làm key dedup
                    cwd = args.get("cwd", "")
                    pattern = args.get("pattern", "")
                    path = f"{cwd}|{pattern}" if pattern else ""
                else:
                    path = args.get("path", "")
                tc_id_to_name[tc.get("id", "")] = (name, path)

    # Tìm các tool_result là read/grep/glob cùng path — chỉ giữ lần cuối
    DEDUPABLE = {"read", "grep", "glob", "view_symbol"}
    # Duyệt ngược: lần đầu gặp (= lần mới nhất) → giữ, sau đó → stub
    seen_file_tool: set[tuple] = set()  # (tool_name, path)
    dedup_stub: set[int] = set()
    for idx in range(len(messages) - 1, -1, -1):
        m = messages[idx]
        if m.get("role") != "tool":
            continue
        tc_id = m.get("tool_call_id", "")
        info = tc_id_to_name.get(tc_id)
        if not info:
            continue
        name, path = info
        if name not in DEDUPABLE or not path:
            continue
        key = (name, path)
        if key in seen_file_tool:
            dedup_stub.add(idx)
        else:
            seen_file_tool.add(key)

    # ── Áp dụng stub ─────────────────────────────────────────────────────────
    all_stub = stub_indices | dedup_stub
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
    STRIP_TOOLS = {"write", "multiedit", "apply_patch", "edit"}
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
            new_tcs = []
            changed = False
            for tc in m["tool_calls"]:
                name = tc.get("function", {}).get("name", "")
                if name in STRIP_TOOLS:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        placeholder = _HISTORY_COMPACTED_MARKER
                        if "content" in args:
                            args["content"] = placeholder
                            changed = True
                        if "patch" in args:
                            args["patch"] = placeholder
                            changed = True
                        if "new_str" in args:
                            args["new_str"] = placeholder
                            changed = True
                        if "edits" in args:
                            for e in args["edits"]:
                                if "new_str" in e:
                                    e["new_str"] = placeholder
                                    changed = True
                        if changed:
                            tc = {**tc, "function": {**tc["function"], "arguments": json.dumps(args)}}
                    except Exception:
                        pass
                new_tcs.append(tc)
            if changed:
                m = {**m, "tool_calls": new_tcs}
        stripped_result.append(m)

    return stripped_result

# ── Per-session file index ───────────────────────────────────────────────────
def _index_key() -> str:
    """Key cho index = absolute path của cwd để tránh xung đột giữa các project
    cùng tên folder (C36 FIX: Path.cwd().name → str(Path.cwd().resolve()))."""
    return str(Path.cwd().resolve())

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
    sid = _project_dir_sid if _project_dir_sid else ""
    fname = f"index_{sid}.json" if sid else "index.json"
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
    if _project_dir_sid:
        legacy = _fw_data_dir() / "index.json"
        if legacy.exists():
            try:
                legacy_index = json.loads(legacy.read_text())
                root = _workspace_root()
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
    rel = abs_path
    # C37 FIX: dùng _workspace_root() thay vì Path.cwd() để key index không có sid/ prefix
    # khi sandbox enforce — tránh AI thấy key "sid/foo.py" mà gọi path sai.
    root = _workspace_root()
    try:
        rel = str(Path(abs_path).resolve().relative_to(root))
    except ValueError:
        try:
            rel = str(Path(abs_path).relative_to(Path.cwd()))
        except ValueError:
            pass
    sym_map = {name: s["line"] for name, s in list(symbols.items())[:40]}
    index[rel] = {
        "path": abs_path,
        "lines": len(content.splitlines()),
        "symbols": sym_map,
        "mtime": time.time(),
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
    if not index:
        return "(no files indexed yet — read a file first)"

    # Lọc: chỉ hiện file trong project_dir thật (không phải placeholder cwd)
    if _project_dir is not None and not _project_dir_is_placeholder:
        proj = _project_dir.resolve()
        index = {
            k: v for k, v in index.items()
            if Path(v["path"]).resolve().is_relative_to(proj)
        }

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
    if _project_dir is not None and not _project_dir_is_placeholder:
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
    root = Path.cwd().resolve()
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

    # Auto-resolve vào sandbox chỉ khi sandbox đã enforce (không phải placeholder)
    if _project_dir is not None and not _project_dir_is_placeholder:
        resolved_p = Path(path).expanduser()
        try:
            resolved_p.resolve().relative_to(_project_dir.resolve())
        except ValueError:
            # Nằm ngoài sandbox → thử resolve vào sandbox
            sandbox_p = _resolve_to_sandbox(path)
            if sandbox_p.exists():
                path = str(sandbox_p)
    err = _check_sandbox_read(path)
    if err: return err
    p = Path(path).expanduser()
    if not p.exists(): return f"[not found: {path}]"
    if p.is_dir():
        # Redirect về project_dir chỉ khi sandbox đã enforce
        if _project_dir is not None and not _project_dir_is_placeholder:
            try:
                p.resolve().relative_to(_project_dir.resolve())
            except ValueError:
                p = _project_dir  # redirect về sandbox
        lines = [f"{p.resolve()}/"]
        lines += _dir_tree(p, "", max_depth=int(depth))
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
    # khiến edit's FileTime safety check (tool_edit) dùng timestamp lỗi thời
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
            f"File: {p}\nLines {start+1}-{min(end, ctotal)} of {ctotal}\n"
            + "─" * 60 + "\n"
            + "\n".join(f"{start+1+i}\t{l}" for i, l in enumerate(sliced))
        )
        remaining = ctotal - end
        if remaining > 0:
            out += f"\n\n(+{remaining} more lines — call read with offset={end+1} if truly needed)"
        _file_read_time[resolved_key] = time.time()
        return out
    # Nếu vừa pop cache vì external edit, bỏ luôn khỏi _recent_writes để
    # nhánh đọc disk thật bên dưới chạy bình thường, không tự coi là "đã biết".
    _recent_writes.discard(resolved_key)

    try:
        all_lines = p.read_text(errors="replace").splitlines()
        total     = len(all_lines)

        # Hard limit: file lớn mà không chỉ định offset → cảnh báo + cắt
        _READ_LARGE_FILE_THRESHOLD = 80  # lines
        warn = ""
        if total > _READ_LARGE_FILE_THRESHOLD and int(offset) == 1 and int(limit) >= total:
            warn = (
                f"[policy] File '{path}' có {total} dòng. "
                f"Đọc toàn bộ file lãng phí token.\n"
                f"Hãy dùng grep/view_symbol để tìm đúng vị trí trước, "
                f"rồi read với offset+limit hẹp.\n"
                f"Ví dụ: grep('tên_hàm') → read(path, offset=N-5, limit=30)\n"
                f"Hiển thị {_READ_LARGE_FILE_THRESHOLD} dòng đầu (tổng {total} dòng):\n"
            )
            limit = _READ_LARGE_FILE_THRESHOLD  # cắt xuống còn threshold

        # Hard block: AI tự ghi limit > 150 mà không qua verify gate
        if int(limit) > 150:
            return (
                f"[policy] limit={limit} quá lớn (tối đa 150).\n"
                f"Dùng grep/view_symbol để tìm chính xác vị trí, "
                f"rồi read với limit ≤ 150 quanh dòng đó.\n"
                f"Ví dụ: grep('keyword') → read(path, offset=N-5, limit=60)"
            )

        # Verify gate: limit > 135 → hỏi user (trừ khi còn credit)
        if int(limit) > 135:
            global _large_read_credits
            if _large_read_credits > 0:
                _large_read_credits -= 1
                limit = 500
            else:
                # BUG FIX (cùng loại đã sửa ở tool_question/tool_verify):
                # trước đây luôn dùng input()/print() thẳng ra CLI, kể cả
                # khi đang chạy /web -- câu hỏi "Cho phép đọc nhiều?" không
                # hề hiện trên web UI, luôn rơi ra cửa sổ CLI phía sau. Sửa
                # theo đúng pattern permission-ask/tool_verify: có state
                # (tham số hoặc fallback qua current_state() nếu gọi nội bộ
                # không truyền tay, vd từ tool_verify) -> state.ask() (web
                # trả lời qua WS); không có state nào cả -> giữ input() cũ.
                _st = state if state is not None else current_state()
                if _st is not None:
                    _st.emit(EV_INFO,
                        text=f"⚠ AI muốn đọc {limit} dòng từ '{path}' — có thể dùng grep để thu hẹp trước.")
                    ans = _st.ask(
                        prompt=f"Cho phép đọc {limit} dòng? Sẽ đọc tối đa 500 dòng, 2 lần.",
                        kind="confirm",
                        default="n",
                    ) or "n"
                    ans = str(ans).strip().lower()
                else:
                    print(f"\n{YELLOW}⚠ AI muốn đọc {limit} dòng từ '{path}'{R}")
                    print(f"{DIM}  Đây là đoạn dài — thường có thể dùng grep để thu hẹp trước.{R}")
                    print(f"{DIM}  Cho phép sẽ đọc tối đa 500 dòng 2 lần.{R}")
                    try:
                        ans = input(f"  {CYAN}Cho phép đọc nhiều? [y/N]: {R}").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        ans = "n"
                if ans in ("y", "yes"):
                    _large_read_credits = 1  # lần này + 1 lần nữa = 2 tổng
                    limit = 500
                    if _st is not None:
                        _st.emit(EV_INFO, text="✓ Cho phép đọc tối đa 500 dòng 2 lần.")
                    else:
                        print(f"  {GREEN}✓ Cho phép đọc tối đa 500 dòng 2 lần.{R}")
                else:
                    return (
                        f"[verify] User từ chối đọc {limit} dòng.\n"
                        f"Hãy dùng grep/view_symbol để thu hẹp vị trí cần đọc,\n"
                        f"rồi read với limit ≤ 135 quanh đúng đoạn cần.\n"
                        f"Ví dụ: grep('keyword') → read(path, offset=N-5, limit=60)"
                    )

        start     = max(0, int(offset) - 1)
        end       = start + int(limit)
        sliced    = all_lines[start:end]
        # Line numbers shown as annotation ONLY — do NOT include them in old_str for edit.
        # The exact file content is the part after the tab on each line.
        out = warn
        out += f"File: {p}\nLines {start+1}-{min(end, total)} of {total}\n"
        out += "NOTE: Line numbers below are display-only. For `edit` old_str, use ONLY the text after the line number, exactly as shown.\n"
        out += "─" * 60 + "\n"
        out += "\n".join(f"{start+1+i}\t{l}" for i, l in enumerate(sliced))
        remaining = total - end
        if remaining > 0:
            out += f"\n\n(+{remaining} more lines — call read with offset={end+1} or use grep to jump to the right section)"
        # Track read time for FileTime safety check
        _file_read_time[str(p.resolve())] = time.time()
        # Cache full content (không phải annotated output) để AI dùng lại
        full_content = "\n".join(all_lines)
        _cache_put(str(p), full_content, _current_sid)
        # Anchor map — AI biết structure file ngay, không cần grep lại turn sau
        amap = _anchor_map(all_lines, focus_line=start)
        if amap:
            out += f"\n\n{amap}"
        return out
    except Exception as e:
        return f"[error: {e}]"

def _check_sandbox_read(path: str) -> str | None:
    """
    Nếu project_dir đã được gán, chỉ cho phép đọc bên trong đó.
    Luôn chặn .fw_data và fw.py bất kể project_dir.
    Trả về error string nếu vi phạm, None nếu OK.
    """
    # Chặn .fw_data tuyệt đối — không ai được đọc thư mục ẩn này
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

    if _project_dir is None or _project_dir_is_placeholder:
        return None  # chua enforce sandbox read — AI doc duoc project co san o cwd
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
    if _contains_compaction_marker(content):
        return _COMPACTION_MARKER_ERROR
    p = _resolve_to_sandbox(path)
    # Giới hạn kích thước hợp lý — chặn model runaway ghi file khổng lồ
    # trên Termux (dung lượng hạn chế). 10MB là dư cho bất kỳ source file thật nào.
    _WRITE_SIZE_LIMIT = 10 * 1024 * 1024
    if len(content.encode("utf-8", errors="replace")) > _WRITE_SIZE_LIMIT:
        return (f"[error] content too large ({len(content):,} chars). "
                f"Limit is {_WRITE_SIZE_LIMIT:,} bytes. "
                f"If this is intentional, split into multiple files or use extract/apply_patch.")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create ("x" mode) — loại race condition TOCTOU giữa check
        # p.exists() và write_text(): nếu file được tạo bởi tiến trình khác
        # (vd bash chạy song song) đúng lúc giữa 2 bước, "x" mode sẽ raise
        # FileExistsError thay vì âm thầm ghi đè.
        try:
            with open(p, "x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            return (f"[error] write only creates new files; '{p}' already exists. "
                    f"Use edit, multiedit, or apply_patch for existing files.")
        before = None  # write chỉ chạy tới đây khi file chưa từng tồn tại
        # Track write time so subsequent edits don't false-alarm on FileTime check
        _file_read_time[str(p.resolve())] = time.time()
        # Update cache ngay — AI không cần read lại file vừa tạo/ghi
        _cache_put(str(p), content, _current_sid)
        _recent_writes.add(str(p.resolve()))  # block read-after-write
        if conn and sid:
            _undo_stack.append(snapshot_save(
                conn, sid, str(p.resolve()), before, content))
            _redo_stack.clear()
        redirected = f" (redirected from {path})" if str(p.resolve()) != str(Path(path).expanduser().resolve()) else ""
        # Inject anchor map — model biết structure ngay, không cần read/glob lại turn sau
        lines = content.splitlines()
        total = len(lines)
        amap = _anchor_map(lines)
        return (f"Written {len(content)} bytes → {p} ({total} lines){redirected}"
                + (f"\n{amap}" if amap else ""))
    except UnicodeEncodeError as e:
        return f"[error: content contains characters that cannot be encoded as UTF-8: {e}]"
    except Exception as e:
        return f"[error: {e}]"


def tool_extract(src, start, end, dst, mode="move", conn=None, sid=None):
    """Lấy nguyên vẹn các dòng [start..end] (1-indexed, inclusive) từ src,
    append vào dst (tạo mới nếu chưa có). mode='move' (default) xoá vùng đó
    khỏi src; mode='copy' giữ src nguyên. Không qua model — tránh việc AI
    đọc rồi gõ lại nội dung khi tách/refactor file."""
    sp = _resolve_to_sandbox(src)
    dp = _resolve_to_sandbox(dst)
    if not sp.exists():
        return f"[not found: {sp}]"
    try:
        src_lines = sp.read_text().splitlines(keepends=True)
        n = len(src_lines)
        if start < 1 or end < start or start > n:
            return f"[error: invalid range {start}-{end} for {sp} ({n} lines)]"
        end = min(end, n)
        chunk = src_lines[start-1:end]
        chunk_text = "".join(chunk)

        dp.parent.mkdir(parents=True, exist_ok=True)
        dst_before = dp.read_text() if dp.exists() else None
        if dst_before is not None and dst_before and not dst_before.endswith("\n"):
            dst_after = dst_before + "\n" + chunk_text
        else:
            dst_after = (dst_before or "") + chunk_text
        dp.write_text(dst_after)
        _cache_put(str(dp), dst_after, _current_sid)
        _file_read_time[str(dp.resolve())] = time.time()
        _recent_writes.add(str(dp.resolve()))
        # C11/C27 FIX: save snapshot cho dst để /undo restore được dst (cả copy lẫn move)
        if conn and sid:
            _undo_stack.append(snapshot_save(
                conn, sid, str(dp.resolve()), dst_before, dst_after))
            _redo_stack.clear()

        result = f"Extracted lines {start}-{end} of {sp} → {dp} ({len(chunk)} lines)"

        if mode == "move":
            src_before = "".join(src_lines)
            new_src_lines = src_lines[:start-1] + src_lines[end:]
            src_after = "".join(new_src_lines)
            sp.write_text(src_after)
            _file_read_time[str(sp.resolve())] = time.time()
            _recent_writes.add(str(sp.resolve()))
            _cache_put(str(sp), src_after, _current_sid)
            if conn and sid:
                _undo_stack.append(snapshot_save(
                    conn, sid, str(sp.resolve()), src_before, src_after))
                # Note: _redo_stack already cleared above for dst snapshot
            result += f"\n[removed from {sp}, {len(new_src_lines)} lines remain]"

        return result
    except Exception as e:
        return f"[error: {e}]"

def tool_edit(path, old_str, new_str, conn=None, sid=None):
    if _contains_compaction_marker(old_str, new_str):
        return _COMPACTION_MARKER_ERROR
    p = _resolve_to_sandbox(path)
    if not p.exists(): return f"[not found: {p}]"
    try:
        # FileTime safety: must have read the file after last external modification
        resolved = str(p.resolve())
        last_read = _file_read_time.get(resolved, 0)
        mtime = p.stat().st_mtime
        if mtime > last_read + 1:
            return (f"[error] File '{path}' has been modified since it was last read "
                    f"(mtime={mtime:.0f}, last_read={last_read:.0f}). "
                    f"Use the read tool to reload it before editing.")
        text  = p.read_text()
        count = text.count(old_str)
        if count == 0:
            # C-fix: thông báo cụ thể hơn để model tự sửa nhanh, không đoán mù.
            snippet = old_str.strip()
            snippet = snippet[:80] + ("…" if len(snippet) > 80 else "")
            hint = (
                f"[error: old_str not found] The exact text you provided does not "
                f"appear in '{path}' (last_read={last_read:.0f}, current mtime={mtime:.0f}).\n"
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
        p.write_text(after)
        # Update read time after our own write so next edit doesn't false-alarm
        _file_read_time[resolved] = time.time()
        # Update cache với content mới — AI thấy thay đổi ngay trong cache block
        _cache_put(str(p), after, _current_sid)
        if conn and sid:
            _undo_stack.append(snapshot_save(
                conn, sid, str(p.resolve()), text, after))
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
    """Apply multiple str-replace edits to a single file sequentially."""
    if _contains_compaction_marker(*[
        v for e in (edits or []) for v in (e.get("old_str"), e.get("new_str"))
    ]):
        return _COMPACTION_MARKER_ERROR
    p = _resolve_to_sandbox(path)
    if not p.exists(): return f"[not found: {p}]"
    results = []
    for i, edit in enumerate(edits):
        old_str = edit.get("old_str", "")
        new_str = edit.get("new_str", "")
        res = tool_edit(str(p), old_str, new_str, conn, sid)
        results.append(f"[edit {i+1}] {res}")
        if res.startswith("[error"):
            results.append(f"[multiedit stopped at edit {i+1} due to error]")
            break
    # Snap tổng hợp sau tất cả edits — AI verify file còn nguyên cấu trúc
    if p.exists():
        final_lines = p.read_text().splitlines()
        snap = _edit_sanity_snap(final_lines, max(0, len(final_lines) // 2))
        if snap:
            results.append(snap)
    return "\n".join(results)


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
