# ── Agent modes ──────────────────────────────────────────────────────────────
AGENT_BUILD = "build"   # full access
AGENT_PLAN  = "plan"    # read-only

# ── Permission levels ────────────────────────────────────────────────────────
PERM_ALLOW = "allow"
PERM_ASK   = "ask"
PERM_DENY  = "deny"

# Default permissions per tool
DEFAULT_PERMS = {
    "bash":        PERM_ASK,    # dangerous — ask by default
    "write":       PERM_ALLOW,
    "extract":     PERM_ALLOW,
    "edit":        PERM_ALLOW,
    "apply_patch": PERM_ALLOW,
    "read":        PERM_ALLOW,
    "glob":        PERM_ALLOW,
    "grep":        PERM_ALLOW,
    "webfetch":    PERM_ALLOW,
    "websearch":   PERM_ALLOW,
    "todowrite":   PERM_ALLOW,
    "todoread":    PERM_ALLOW,
    "question":    PERM_ALLOW,
    "task":        PERM_ALLOW,
    "skill":       PERM_ALLOW,
    "lsp":         PERM_ALLOW,
}

# Plan-mode overrides (read-only)
PLAN_PERMS = {
    "bash":        PERM_ASK,
    "write":       PERM_DENY,
    "extract":     PERM_DENY,
    "edit":        PERM_DENY,
    "apply_patch": PERM_DENY,
}

# Skills search paths
SKILLS_DIRS = [
    Path.cwd() / FW_DATA_NAME / "skills",      # project-local (chính)
    Path.cwd() / ".opencode" / "skills",        # opencode compat
]


# AGENTS.md / rules search paths (opencode compatible)
AGENTS_FILES = [
    Path.cwd() / "AGENTS.md",
    Path.cwd() / "CLAUDE.md",              # claude-code compat
    Path.home() / ".config" / "opencode" / "AGENTS.md",
    Path.cwd() / FW_DATA_NAME / "AGENTS.md",  # fw project-local
    Path.home() / ".claude" / "CLAUDE.md", # claude-code global compat
]

# Cache AGENTS.md: key=(path, mtime) → tránh đọc file mỗi turn
_agents_cache: dict = {}   # path_str → (mtime, text)
_agents_combined_cache: tuple = (None, "")  # (fingerprint, combined_text)

def load_agents_md(extra_dirs: list[Path] | None = None) -> str:
    """Load AGENTS.md / rules files, cache theo mtime để không đọc lại mỗi turn."""
    global _agents_combined_cache

    def _read_cached(p: Path) -> str:
        """Đọc file, cache theo mtime. Trả về "" nếu không đổi."""
        try:
            mtime = p.stat().st_mtime
        except Exception:
            return ""
        key = str(p)
        cached = _agents_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            text = p.read_text().strip()
            _agents_cache[key] = (mtime, text)
            return text
        except Exception:
            return ""

    found = []
    # project-level: traverse up từ cwd
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        for name in ("AGENTS.md", "CLAUDE.md"):
            p = parent / name
            if p.exists():
                text = _read_cached(p)
                if text:
                    found.append(f"# Rules from {p}\n\n{text}")
                break
        if found:
            break
    # global
    for gp in [
        Path.home() / ".config" / "opencode" / "AGENTS.md",
        Path.cwd() / FW_DATA_NAME / "AGENTS.md",
        Path.home() / ".claude" / "CLAUDE.md",
    ]:
        if gp.exists():
            text = _read_cached(gp)
            if text:
                found.append(f"# Global rules from {gp}\n\n{text}")
            break
    return "\n\n".join(found) if found else ""

# Custom commands: loaded from .fw_data/commands/*.md và .opencode/commands/*.md
COMMANDS_DIRS = [
    Path.cwd() / FW_DATA_NAME / "commands",    # project-local (chính)
    Path.cwd() / ".opencode" / "commands",      # opencode compat
    Path.home() / ".config" / "opencode" / "commands",
]

def load_custom_commands() -> dict:
    """
    Load custom slash commands from .opencode/commands/*.md
    Returns {name: {template, description, agent, model, subtask}}
    """
    commands = {}
    for cmd_dir in COMMANDS_DIRS:
        if not cmd_dir.exists():
            continue
        for f in sorted(cmd_dir.glob("*.md")):
            name = f.stem.lower()
            try:
                raw = f.read_text()
            except Exception:
                continue
            # Parse optional YAML-ish frontmatter (--- ... ---)
            meta = {}
            template = raw
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    fm, template = parts[1], parts[2].strip()
                    for line in fm.splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            meta[k.strip().lower()] = v.strip()
            commands[name] = {
                "template":    template,
                "description": meta.get("description", f"Custom command: {name}"),
                "agent":       meta.get("agent", ""),
                "model":       meta.get("model", ""),
                "subtask":     meta.get("subtask", "").lower() == "true",
                "file":        str(f),
            }
    return commands

# Global undo stack  [{path: str, before: str|None, after: str}]
_undo_stack: list = []
_redo_stack: list = []

# ── File cache ────────────────────────────────────────────────────────────────
# Lưu nội dung + symbol map của file đã đọc/ghi trong session.
# AI thấy cache trong system prompt → không cần read lại file đã biết.
# Cache tự update sau mỗi write/edit → không bao giờ stale.
_file_cache: dict = {}  # {abs_path: {"content": str, "symbols": dict, "mtime": float, "access": float}}

# ── Bug 1 fix: LRU limits ─────────────────────────────────────────────────────
CACHE_MAX_FILES  = 6      # tối đa N file trong cache block (LRU — file cũ nhất bị drop khỏi prompt)
CACHE_MAX_CHARS  = 5_000  # tổng ký tự inject vào system prompt, không vượt quá

# ── Memory pressure eviction ──────────────────────────────────────────────────
# Evict _file_cache entries khi RAM cao để tránh OOM trên Android.
# Ngưỡng: soft=50%, hard=65%, critical=80% tổng RAM.
# Kích hoạt sau mỗi batch tool calls từ agent_turn().
_MEM_SOFT     = float(os.environ.get("FW_MEM_SOFT",     "0.50"))
_MEM_HARD     = float(os.environ.get("FW_MEM_HARD",     "0.65"))
_MEM_CRITICAL = float(os.environ.get("FW_MEM_CRITICAL", "0.80"))
_MEM_COOLDOWN = 5.0   # giây giữa 2 lần evict liên tiếp
_mem_last_evict: float = 0.0

def _mem_ratio() -> float:
    """RSS / total RAM. Trả về 0.0 nếu không đọc được."""
    try:
        import resource as _res
        rss   = _res.getrusage(_res.RUSAGE_SELF).ru_maxrss
        # Linux: KB, macOS: bytes
        rss_bytes = rss * 1024 if sys.platform != "darwin" else rss
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return rss_bytes / total if total > 0 else 0.0
    except Exception:
        return 0.0

def memory_pressure_evict() -> None:
    """
    Evict _file_cache theo mức RAM:
    - soft  (≥50%): xóa entry không access trong 60 phút.
    - hard  (≥65%): xóa entry không access trong 30 phút.
    - critical (≥80%): clear toàn bộ cache.
    Có cooldown 5s để không spam khi nhiều tool calls liên tiếp.
    """
    global _mem_last_evict
    if not _file_cache:
        return
    now = time.time()
    if now - _mem_last_evict < _MEM_COOLDOWN:
        return
    ratio = _mem_ratio()
    if ratio < _MEM_SOFT:
        return
    _mem_last_evict = now
    if ratio >= _MEM_CRITICAL:
        _file_cache.clear()
        if _cache_debug:
            print(f"  {RED}[cache mem]{R} critical ({ratio:.0%}) → clear all")
        return
    cutoff_min = 30 if ratio >= _MEM_HARD else 60
    cutoff_ts  = now - cutoff_min * 60
    stale = [k for k, v in _file_cache.items() if v.get("access", 0) < cutoff_ts]
    for k in stale:
        _file_cache.pop(k, None)
    if stale and _cache_debug:
        level = "hard" if ratio >= _MEM_HARD else "soft"
        print(f"  {YELLOW}[cache mem]{R} {level} ({ratio:.0%}) → evict {len(stale)} entries")

# ── Bug 3 fix: symbol parsing mạnh hơn ───────────────────────────────────────
def _parse_symbols(content: str, ext: str = "") -> dict:
    """
    Parse symbols (function/class/variable) từ content.
    Hỗ trợ: Python, JS/TS (kể cả arrow function lồng, destructuring), HTML id/class.
    Trả về {name: {"line": int, "snippet": str}}
    """
    symbols = {}
    lines   = content.splitlines()

    # HTML: tìm id= và các tag có ý nghĩa (button, input, form, div có id)
    if ext in (".html", ".htm"):
        for i, line in enumerate(lines, 1):
            # id="foo" hoặc id='foo'
            for m in re.finditer(r'\bid=["\'](\w[\w\-]*)["\']', line):
                name = m.group(1)
                symbols[f"#{name}"] = {"line": i, "snippet": line.strip()[:70]}
            # class="foo bar" — lấy từng class
            for m in re.finditer(r'\bclass=["\']([^"\']+)["\']', line):
                for cls in m.group(1).split():
                    if cls not in symbols:
                        symbols[f".{cls}"] = {"line": i, "snippet": line.strip()[:70]}
        return symbols

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "/*", "*")):
            continue

        # ── Python ──────────────────────────────────────────────────────────
        m = re.match(r'^(async\s+)?def\s+(\w+)\s*[\(:]', stripped)
        if m:
            symbols[m.group(2)] = {"line": i, "snippet": stripped[:70]}
            continue
        m = re.match(r'^class\s+(\w+)', stripped)
        if m:
            symbols[m.group(1)] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── JS/TS: named function declaration ────────────────────────────────
        m = re.match(r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*[\(<]', stripped)
        if m:
            symbols[m.group(1)] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── JS/TS: class ─────────────────────────────────────────────────────
        m = re.match(r'^(?:export\s+)?(?:default\s+)?class\s+(\w+)', stripped)
        if m:
            symbols[m.group(1)] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── JS/TS: const/let/var foo = ... (arrow, function, value) ─────────
        # Bắt cả: const foo = () => / const foo = async () => / const foo = function
        m = re.match(r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\(|function|\w+\s*=>)', stripped)
        if m:
            symbols[m.group(1)] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── JS/TS: destructuring: const { foo, bar } = ... ──────────────────
        m = re.match(r'^(?:export\s+)?(?:const|let|var)\s*\{([^}]+)\}\s*=', stripped)
        if m:
            for name in re.findall(r'\b(\w+)\b', m.group(1)):
                if name not in ("default",):
                    symbols[name] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── JS/TS: object method shorthand: foo() { / async foo() { ─────────
        m = re.match(r'^(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{', stripped)
        if m and m.group(1) not in ("if", "for", "while", "switch", "catch"):
            symbols[m.group(1)] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── JS/TS: module.exports.foo = / exports.foo = ──────────────────────
        m = re.match(r'^(?:module\.)?exports\.(\w+)\s*=', stripped)
        if m:
            symbols[m.group(1)] = {"line": i, "snippet": stripped[:70]}
            continue

        # ── CSS: selector (chỉ parse .fw và #fw-style selectors) ────────────
        if ext in (".css", ".scss", ".sass", ".less"):
            m = re.match(r'^([.#][\w\-]+(?:\s*,\s*[.#][\w\-]+)*)\s*\{', stripped)
            if m:
                for sel in m.group(1).split(","):
                    sel = sel.strip()
                    if sel:
                        symbols[sel] = {"line": i, "snippet": stripped[:70]}
                continue

    return symbols

# Debug mode — bật bằng env FW_CACHE_DEBUG=1 hoặc /cache debug on
_cache_debug: bool = os.environ.get("FW_CACHE_DEBUG", "").strip() == "1"

def _cache_log(op: str, path: str, extra: str = ""):
    """In log cache nếu debug mode bật. op: '+' add, '-' drop, '~' update, '?' stale"""
    if not _cache_debug:
        return
    rel = path
    try:
        rel = str(Path(path).relative_to(Path.cwd()))
    except ValueError:
        pass
    icons = {"+": GREEN, "-": RED, "~": YELLOW, "?": CYAN}
    color = icons.get(op, DIM)
    extra_str = f"  {DIM}{extra}{R}" if extra else ""
    print(f"  {color}[cache {op}]{R} {DIM}{rel}{R}{extra_str}")

def _content_hash(content: str) -> str:
    """
    Hash content để detect thay đổi chính xác hơn mtime.
    File nhỏ (< 50KB): hash full. File lớn: sample first+last 4KB.
    """
    import hashlib
    sample = content[:4096] + content[-4096:] if len(content) > 50_000 else content
    return hashlib.md5(sample.encode(errors="replace")).hexdigest()[:12]

def _cache_put(path: str, content: str, sid: str = ""):
    """Lưu file vào cache sau khi đọc hoặc ghi. Cập nhật access time cho LRU."""
    p   = Path(path).expanduser().resolve()
    ext = p.suffix.lower()
    now = time.time()
    key = str(p)
    op  = "~" if key in _file_cache else "+"
    # Dùng mtime thực từ disk thay vì time.time() — tránh clock skew giữa
    # Python process time và filesystem time (Android FAT32, network FS, Termux).
    try:
        disk_mtime = p.stat().st_mtime
    except Exception:
        disk_mtime = now
    _file_cache[key] = {
        "content": content,
        "symbols": _parse_symbols(content, ext),
        "mtime":   disk_mtime,
        "access":  now,
        "hash":    _content_hash(content),  # hash check — chính xác hơn mtime trên Android
    }
    _cache_log(op, key, f"{len(content)} chars  hash={_file_cache[key]['hash']}")
    if sid:
        _index_update(key, content, _file_cache[key]["symbols"])

def _cache_touch(path: str):
    """Cập nhật access time khi file được dùng (LRU)."""
    key = str(Path(path).expanduser().resolve())
    if key in _file_cache:
        _file_cache[key]["access"] = time.time()
        _cache_log("~", key, "touch")

def _cache_invalidate(path: str):
    """
    Xoá cache khi file bị xoá hoặc external-modified.
    Hash check: đọc content thật → so hash — chính xác hơn mtime trên Termux/Android.
    Fallback về mtime nếu file lớn (tránh đọc file MB chỉ để check).
    """
    key = str(Path(path).expanduser().resolve())
    if key not in _file_cache:
        return
    p = Path(key)
    if not p.exists():
        _cache_log("-", key, "file deleted")
        _file_cache.pop(key, None)
        return
    try:
        cached_hash  = _file_cache[key].get("hash", "")
        cached_mtime = _file_cache[key]["mtime"]
        real_mtime   = p.stat().st_mtime

        # Fast path: mtime chưa đổi → skip hash (tránh đọc file không cần thiết)
        if real_mtime <= cached_mtime + 1:
            return

        # mtime đổi → kiểm tra hash để phân biệt:
        # (a) agent tự ghi (mtime mới nhưng hash vẫn đúng) → giữ cache
        # (b) external edit (hash khác) → drop cache
        if cached_hash:
            # Sample hash handle được cả file lớn — không cần giới hạn size
            real_content = p.read_text(errors="replace")
            real_hash    = _content_hash(real_content)
            if real_hash == cached_hash:
                # Hash khớp — chỉ mtime drift (Android FAT32 resolution thấp)
                _file_cache[key]["mtime"] = real_mtime  # sync lại mtime
                return
            _cache_log("-", key, f"external edit detected (hash {cached_hash} → {real_hash})")
        else:
            _cache_log("-", key, "mtime changed, no hash")

        _file_cache.pop(key, None)

    except Exception as e:
        _cache_log("?", key, f"check error: {e}")

def _cache_validate_all():
    """Quét toàn cache trước mỗi turn — drop entry nào stale."""
    for key in list(_file_cache.keys()):
        _cache_invalidate(key)

def _build_cache_block(turn_files: set = None, prev_injected: set = None) -> tuple:
    """
    Inject file context vào user message.
    - batch mode: delta — chỉ inject file MỚI, file cũ list tên ngắn
    - sequential mode: inject tất cả file turn này (1 step nên không cần delta)
    Trả về (block_str, new_prev_injected).
    """
    if not _file_cache:
        return "", prev_injected or set()

    prev = prev_injected or set()

    turn_keys = set()
    if turn_files:
        for p in turn_files:
            turn_keys.add(str(Path(p).expanduser().resolve()))

    # Delta: chỉ inject file chưa inject step nào trước đó
    new_keys = turn_keys - prev
    old_keys = turn_keys & prev

    new_entries = [(k, _file_cache[k]) for k in new_keys if k in _file_cache]
    new_entries.sort(key=lambda kv: kv[1]["access"], reverse=True)

    if not new_entries and not old_keys:
        return "", prev

    lines = ["\n\n# File context:"]
    total_chars = 0

    for abs_path, info in new_entries[:CACHE_MAX_FILES]:
        content  = info["content"]
        symbols  = info["symbols"]
        rel      = abs_path
        try:
            rel = str(Path(abs_path).relative_to(Path.cwd()))
        except ValueError:
            pass

        lines_list = content.splitlines()
        line_count = len(lines_list)
        char_count = len(content)
        header     = f"\n## {rel}  ({line_count} lines)"

        if char_count <= 200:
            block = f"```\n{content}\n```"
        elif symbols:
            sym_lines = [f"  - {name} @ line {s['line']}: {s['snippet']}"
                         for name, s in list(symbols.items())[:25]]
            if len(symbols) > 25:
                sym_lines.append(f"  ... (+{len(symbols)-25} more)")
            block = "Symbol map:\n" + "\n".join(sym_lines)
        else:
            preview = "\n".join(f"  {l}" for l in lines_list[:5])
            tail    = f"\n  ... (+{line_count - 5} more lines)" if line_count > 5 else ""
            block   = f"Preview ({line_count} lines):\n{preview}{tail}"

        entry_chars = len(header) + len(block)
        if total_chars + entry_chars > CACHE_MAX_CHARS:
            break
        lines.append(header)
        lines.append(block)
        total_chars += entry_chars

    # File đã inject rồi: chỉ list tên (batch mode)
    if old_keys:
        old_lines = ["\n# Already in context:"]
        for k in old_keys:
            if k not in _file_cache:
                continue
            rel = k
            try:
                rel = str(Path(k).relative_to(Path.cwd()))
            except ValueError:
                pass
            lc = len(_file_cache[k]["content"].splitlines())
            old_lines.append(f"  {rel} ({lc} lines)")
        lines.extend(old_lines)

    return "\n".join(lines), prev | new_keys

# ── Project dir sandbox ──────────────────────────────────────────────────────
# Stores the project directory for the current session.
# Set once (on first write) and locked for the rest of the session.
_project_dir: Path | None = None
_project_dir_conn = None
_project_dir_sid  = ""
_project_dir_is_placeholder: bool = False  # True khi set là cwd eager-init, chưa tạo subdir thật

def _sandbox_init(conn, sid, project_dir_str: str | None):
    """Called at session start to restore or reset the sandbox.
    Eager init: gán _project_dir ngay từ đầu để system prompt ổn định từ turn 1,
    tránh cache miss lần đầu khi _project_dir được set muộn (sau write đầu tiên).
    """
    global _project_dir, _project_dir_conn, _project_dir_sid, _project_dir_is_placeholder
    _project_dir_conn = conn
    _project_dir_sid  = sid
    if project_dir_str:
        # Có từ session đã lưu — dùng luôn
        _project_dir = Path(project_dir_str)
        _project_dir_is_placeholder = False
    else:
        # Session mới: pre-set bằng cwd để system prompt cache ổn định ngay turn 1.
        # _ensure_project_dir vẫn tạo subdir thực sự lúc write đầu tiên,
        # nhưng proj_key đã stable từ đây → không phá cache prefix.
        _project_dir = Path.cwd()
        _project_dir_is_placeholder = True

def _ensure_project_dir(requested_path: str) -> Path:
    """
    On the FIRST write of a session, auto-create a project subdir inside cwd.
    The name is derived from the requested path's top-level component.
    Returns the resolved Path (may differ from original).
    """
    global _project_dir, _project_dir_is_placeholder
    # Nếu đã có project_dir thật (không phải placeholder cwd), dùng luôn
    if _project_dir is not None and not _project_dir_is_placeholder:
        return _project_dir

    p = Path(requested_path)

    # Ưu tiên: lấy component đầu tiên của path gốc (relative hay absolute)
    # myapp/utils.py → myapp
    # /abs/path/myapp/utils.py → thử relative_to cwd trước
    folder_name = ""

    # Nếu path có nhiều hơn 1 component → lấy component đầu
    # (cả relative lẫn absolute đều xử lý được)
    try:
        rel = p.relative_to(Path.cwd())
        folder_name = rel.parts[0] if len(rel.parts) > 1 else ""
    except ValueError:
        pass

    if not folder_name:
        # Path relative không qua cwd: lấy parts[0] trực tiếp
        parts = p.parts
        if len(parts) > 1:
            # Bỏ qua '/' nếu absolute
            folder_name = parts[1] if p.is_absolute() else parts[0]
        else:
            # File không có thư mục cha → dùng stem làm folder
            folder_name = p.stem or "project"

    # Sanitise: only keep alphanumeric, dash, underscore, dot
    folder_name = re.sub(r"[^\w.\-]", "_", folder_name) or "project"

    proj = Path.cwd() / folder_name
    proj.mkdir(parents=True, exist_ok=True)

    _project_dir = proj
    _project_dir_is_placeholder = False
    # Invalidate system prompt cache — proj_key vừa đổi từ "" → path thật,
    # buộc build_system() build lại với sandbox section đúng ở step tiếp theo.
    _system_full_cache.clear()
    if _project_dir_conn and _project_dir_sid:
        session_update(_project_dir_conn, _project_dir_sid,
                       project_dir=str(proj.resolve()))
    print(f"  {GREEN}[sandbox]{R} project_dir gán: {DIM}{proj}{R}")
    return proj

def _resolve_to_sandbox(path: str) -> Path:
    """
    Tự động redirect path vào project_dir (tạo nếu chưa có).
    - Nếu path đã nằm trong project_dir → giữ nguyên.
    - Nếu path là relative hoặc nằm ngoài → rewrite vào project_dir,
      giữ lại cấu trúc thư mục con tương đối nếu có.
    Dùng chung cho write / edit / apply_patch.
    """
    proj = _ensure_project_dir(path)
    p_orig = Path(path).expanduser()

    # Đã nằm trong project_dir rồi → không đổi
    try:
        p_orig.resolve().relative_to(proj.resolve())
        return p_orig
    except ValueError:
        pass

    # Nằm trong cwd nhưng ngoài project_dir → giữ relative path từ cwd
    try:
        rel = p_orig.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        # Absolute hoàn toàn ngoài cwd → chỉ lấy phần tên file/subpath
        rel = Path(*p_orig.parts[1:]) if p_orig.is_absolute() else Path(p_orig.name)

    return proj / rel

# ════════════════════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════════════════════

def db_connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            directory    TEXT NOT NULL,
            model        TEXT NOT NULL,
            agent        TEXT NOT NULL DEFAULT 'build',
            created_at   INTEGER NOT NULL,
            updated_at   INTEGER NOT NULL,
            token_input  INTEGER DEFAULT 0,
            token_output INTEGER DEFAULT 0,
            token_cached INTEGER DEFAULT 0,
            project_dir  TEXT,
            provider     TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS message (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            created_at  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS todo (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
            content     TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            priority    TEXT NOT NULL DEFAULT 'medium',
            updated_at  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS file_snapshot (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
            path        TEXT NOT NULL,
            before      TEXT,
            after       TEXT NOT NULL,
            created_at  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS checkpoint (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
            label       TEXT NOT NULL,
            summary     TEXT NOT NULL,
            created_at  INTEGER NOT NULL
        );
        -- Migration: add agent column if missing
        CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    # Migration: add project_dir column if missing (older DBs)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(session)").fetchall()]
    if "project_dir" not in cols:
        conn.execute("ALTER TABLE session ADD COLUMN project_dir TEXT")
        conn.commit()
    if "token_cached" not in cols:
        conn.execute("ALTER TABLE session ADD COLUMN token_cached INTEGER DEFAULT 0")
        conn.commit()
    if "provider" not in cols:
        conn.execute("ALTER TABLE session ADD COLUMN provider TEXT DEFAULT ''")
        conn.commit()
    conn.commit()
    return conn

def session_create(conn, model, title="", agent=AGENT_BUILD):
    sid = str(uuid.uuid4())[:8]
    now = int(time.time())
    if not title:
        title = f"Session {datetime.fromtimestamp(now).strftime('%m-%d %H:%M')}"
    conn.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,0,0,0,NULL,?)",
                 (sid, title, os.getcwd(), model, agent, now, now, _active_provider))
    conn.commit()
    return {"id": sid, "title": title, "directory": os.getcwd(),
            "model": model, "agent": agent, "project_dir": None,
            "provider": _active_provider}

def session_list(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM session ORDER BY updated_at DESC LIMIT 20").fetchall()]

def session_update(conn, sid, **kw):
    kw["updated_at"] = int(time.time())
    sets = ", ".join(f"{k}=?" for k in kw)
    conn.execute(f"UPDATE session SET {sets} WHERE id=?", (*kw.values(), sid))
    conn.commit()

def _normalize_message(role, raw):
    """
    Convert any stored message to OpenAI/Fireworks wire format.
    Handles old Anthropic-format assistant messages that have list content
    with type:tool_use blocks.
    """
    # If content is a plain string, wrap as-is
    if isinstance(raw, str):
        return {"role": role, "content": raw}

    # If it's already an OpenAI-style assistant msg with tool_calls key
    if isinstance(raw, dict) and "tool_calls" in raw:
        return raw  # already correct

    # If content is a list (possible Anthropic format or mixed)
    if isinstance(raw, list):
        # Check for Anthropic tool_use blocks
        tool_use_blocks = [b for b in raw if isinstance(b, dict) and b.get("type") == "tool_use"]
        text_blocks     = [b for b in raw if isinstance(b, dict) and b.get("type") == "text"]
        if tool_use_blocks and role == "assistant":
            # Convert to OpenAI format
            text_content = text_blocks[0]["text"] if text_blocks else None
            tool_calls = [{
                "id":       b["id"],
                "type":     "function",
                "function": {
                    "name":      b["name"],
                    "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)
                }
            } for b in tool_use_blocks]
            return {"role": "assistant", "content": text_content, "tool_calls": tool_calls}
        # Plain list content (e.g. multi-part user message) — keep as-is
        # but Fireworks only accepts string content for most roles, so flatten
        text = " ".join(b.get("text", "") for b in raw if isinstance(b, dict))
        return {"role": role, "content": text or str(raw)}

    # Tool result stored as dict {role, tool_call_id, content}
    if isinstance(raw, dict):
        if role == "tool" and "tool_call_id" in raw:
            return raw  # already correct wire format
        return {"role": role, "content": raw.get("content", str(raw))}

    return {"role": role, "content": str(raw)}

def messages_load(conn, sid):
    rows = conn.execute(
        "SELECT role,content FROM message WHERE session_id=? ORDER BY created_at",
        (sid,)).fetchall()
    result = []
    for r in rows:
        raw = json.loads(r["content"])
        msg = _normalize_message(r["role"], raw)
        result.append(msg)
    return result

def message_save(conn, sid, role, content):
    conn.execute("INSERT INTO message VALUES (?,?,?,?,?)",
                 (str(uuid.uuid4()), sid, role,
                  json.dumps(content, ensure_ascii=False), int(time.time())))
    conn.execute("UPDATE session SET updated_at=? WHERE id=?", (int(time.time()), sid))
    conn.commit()

def checkpoint_save(conn, sid, label: str, messages: list | None = None,
                    summary: str = "") -> str:
    """Persist a progress marker without injecting it into model context."""
    now = int(time.time())
    label = (label or "checkpoint").strip()[:80]
    if not summary and messages:
        user_count = sum(1 for m in messages if m.get("role") == "user")
        assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
        tool_count = sum(1 for m in messages if m.get("role") == "tool")
        summary = f"{user_count} user, {assistant_count} assistant, {tool_count} tool messages"
    summary = (summary or "manual checkpoint").strip()[:500]
    cid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO checkpoint VALUES (?,?,?,?,?)",
                 (cid, sid, label, summary, now))
    conn.execute("UPDATE session SET updated_at=? WHERE id=?", (now, sid))
    conn.commit()
    return cid

def checkpoints_load(conn, sid, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM checkpoint WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
        (sid, int(limit))
    ).fetchall()
    return [dict(r) for r in rows]

def messages_replace_all(conn, sid, messages):
    conn.execute("DELETE FROM message WHERE session_id=?", (sid,))
    ts = int(time.time())
    for i, m in enumerate(messages):
        conn.execute("INSERT INTO message VALUES (?,?,?,?,?)",
                     (str(uuid.uuid4()), sid, m["role"],
                      json.dumps(m["content"], ensure_ascii=False), ts + i))
    conn.commit()

