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
# Giữ hành vi cũ (shell=True) nhưng thêm confirm + allowlist tối thiểu.
# Có 2 lớp permission độc lập:
#   Lớp 1 — _check_permission() trong 10_main.py: hỏi "Allow? [y/N/a]"
#            /perm bash allow chỉ ảnh hưởng lớp này (bỏ câu hỏi confirm).
#   Lớp 2 — allowlist dưới đây (_BASH_ALLOW_RE / _BASH_CONFIRMED): chặn
#            lệnh không nằm trong danh sách (git/pytest/python/node/npm/make).
#            /perm bash allow KHÔNG tắt lớp này — 2 lớp hoàn toàn độc lập.
#            _BASH_CONFIRMED chỉ tự set True khi 1 lệnh hợp lệ đã chạy qua.
_BASH_CONFIRM_EVERY_SESSION = True
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
_BASH_CONFIRMED = False

# Pattern chặn file inspection qua bash — AI phải dùng read/glob/grep thay thế
# head/tail chỉ block khi đứng đầu lệnh (không phải sau pipe)
_BASH_INSPECT_PATTERNS = [
    r"(?:^|&&|;)\s*cat\s+\S",           # cat <file> (không phải | cat)
    r"(?:^|&&|;)\s*less\s+\S",          # less <file>
    r"(?:^|&&|;)\s*head\s+",            # head ... ở đầu lệnh
    r"(?:^|&&|;)\s*tail\s+",            # tail ... ở đầu lệnh
    r"(?:^|&&|;|\|)\s*ls\s+-[a-zA-Z]*R",# ls -R, ls -lR ở bất kỳ đâu
    r"(?:^|&&|;)\s*find\s+[./]",        # find . / find ./dir ở đầu lệnh
]
_BASH_INSPECT_RE = re.compile("|".join(_BASH_INSPECT_PATTERNS))

def tool_bash(command, timeout=30):
    # Chặn file inspection qua bash — AI phải dùng read/glob/grep thay thế
    if _BASH_INSPECT_RE.search(command):
        return (
            "[policy] Không được dùng bash để đọc/liệt kê file.\n"
            "Dùng các tool chuyên dụng thay thế:\n"
            "  • cat / head / tail / less  → read(path, offset, limit)\n"
            "  • ls -R / find .            → glob(pattern) hoặc read(dir)\n"
            "Lý do: bash file inspection lãng phí token, phá cache context."
        )



    # ── Allowlist + confirm gate (minimal) ─────────────────────────────────
    global _BASH_CONFIRMED
    if _BASH_CONFIRM_EVERY_SESSION and not _BASH_CONFIRMED:
        # Nếu lệnh không nằm trong allowlist → yêu cầu confirm qua permission layer
        if not _BASH_ALLOW_RE.search(command.strip()):
            return (
                "[policy] bash command blocked by allowlist.\n"
                "Hãy dùng lệnh trong allowlist (git/pytest/python/node/npm/make) hoặc\n"
                "đổi strategy (tools read/write/edit/apply_patch)."
            )
        _BASH_CONFIRMED = True
    if _project_dir is not None:
        proj = _project_dir.resolve()

        # Chặn lệnh cố escape khỏi sandbox
        if _BASH_DENY_RE.search(command):
            return (f"[sandbox] Lệnh bị chặn: không được thoát khỏi project_dir.\n"
                    f"Chỉ được thao tác bên trong: {proj}\n"
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
    import re as _re

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
                        placeholder = "[content omitted from history — outcome was reported in tool result at the time]"
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
    """<cwd>/.fw_data/index.json — lưu cạnh project, ẩn khỏi mọi tool."""
    return _fw_data_dir() / "index.json"

def _index_load() -> dict:
    """Load index cho project hiện tại. Trả về {} nếu chưa có."""
    p = _index_path()
    try:
        if p.exists():
            return json.loads(p.read_text())
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

def tool_read(path, offset=1, limit=READ_DEFAULT_LIMIT, depth=4):

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
        return out

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

def tool_write(path, content, conn=None, sid=None):
    p = _resolve_to_sandbox(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        before = p.read_text() if p.exists() else None
        p.write_text(content)
        # Track write time so subsequent edits don't false-alarm on FileTime check
        _file_read_time[str(p.resolve())] = time.time()
        # Update cache ngay — AI không cần read lại file vừa tạo/ghi
        _cache_put(str(p), content, _current_sid)
        _recent_writes.add(str(p.resolve()))  # block read-after-write
        if conn and sid:
            snapshot_save(conn, sid, str(p.resolve()), before, content)
            _undo_stack.append({"path": str(p.resolve()), "before": before, "after": content})
            _redo_stack.clear()
        redirected = f" (redirected from {path})" if str(p.resolve()) != str(Path(path).expanduser().resolve()) else ""
        # Inject anchor map — model biết structure ngay, không cần read/glob lại turn sau
        lines = content.splitlines()
        total = len(lines)
        amap = _anchor_map(lines)
        return (f"Written {len(content)} bytes → {p} ({total} lines){redirected}"
                + (f"\n{amap}" if amap else ""))
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
            snapshot_save(conn, sid, str(dp.resolve()), dst_before or "", dst_after)
            _undo_stack.append({"path": str(dp.resolve()), "before": dst_before or "", "after": dst_after})
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
                snapshot_save(conn, sid, str(sp.resolve()), src_before, src_after)
                _undo_stack.append({"path": str(sp.resolve()), "before": src_before, "after": src_after})
                # Note: _redo_stack already cleared above for dst snapshot
            result += f"\n[removed from {sp}, {len(new_src_lines)} lines remain]"

        return result
    except Exception as e:
        return f"[error: {e}]"

def tool_edit(path, old_str, new_str, conn=None, sid=None):
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
        if count == 0: return "[error: old_str not found]"
        if count > 1:  return f"[error: found {count} times — must be unique]"
        after = text.replace(old_str, new_str, 1)
        p.write_text(after)
        # Update read time after our own write so next edit doesn't false-alarm
        _file_read_time[resolved] = time.time()
        # Update cache với content mới — AI thấy thay đổi ngay trong cache block
        _cache_put(str(p), after, _current_sid)
        if conn and sid:
            snapshot_save(conn, sid, str(p.resolve()), text, after)
            _undo_stack.append({"path": str(p.resolve()), "before": text, "after": after})
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


