# ── Diff display ─────────────────────────────────────────────────────────────
def _format_diff(old_str: str, new_str: str, context: int = 2) -> str:
    """Render a compact unified diff with red/green colors."""
    old_lines = old_str.splitlines(keepends=True)
    new_lines = new_str.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines,
                                     fromfile="old", tofile="new",
                                     n=context))
    if not diff:
        return f"{DIM}(no changes){R}"
    out = []
    for line in diff:
        line_s = line.rstrip("\n")
        if line_s.startswith("---") or line_s.startswith("+++"):
            out.append(f"{DIM}{line_s}{R}")
        elif line_s.startswith("@@"):
            out.append(f"{CYAN}{line_s}{R}")
        elif line_s.startswith("-"):
            out.append(f"{RED}{line_s}{R}")
        elif line_s.startswith("+"):
            out.append(f"{GREEN}{line_s}{R}")
        else:
            out.append(f"{DIM}{line_s}{R}")
    return "\n".join(out)

def _explain_tool_action(name: str, args: dict) -> str:
    """
    Return a human-readable one-liner explaining what the tool will DO,
    shown above the y/N prompt so user knows what they're approving.
    """
    try:
        if name == "bash":
            cmd = args.get("command", "")
            # Truncate very long commands but show the beginning
            display = cmd if len(cmd) <= 120 else cmd[:117] + "..."
            return f"{YELLOW}Run shell command:{R}\n  {BOLD}{display}{R}"

        if name == "write":
            p    = args.get("path", "?")
            size = len(args.get("content", ""))
            existing = Path(p).exists()
            action = "Overwrite" if existing else "Create new file"
            return f"{YELLOW}{action}:{R} {BOLD}{p}{R}  {DIM}({size:,} chars){R}"

        if name == "extract":
            src   = args.get("src", "?")
            dst   = args.get("dst", "?")
            start = args.get("start", "?")
            end   = args.get("end", "?")
            mode  = args.get("mode", "move")
            verb  = "Move" if mode == "move" else "Copy"
            return f"{YELLOW}{verb} lines {start}-{end}:{R} {BOLD}{src}{R} → {BOLD}{dst}{R}"

        if name == "edit":
            p       = args.get("path", "?")
            old_str = args.get("old_str", "")
            new_str = args.get("new_str", "")
            diff    = _format_diff(old_str, new_str)
            return (f"{YELLOW}Edit file:{R} {BOLD}{p}{R}\n"
                    f"{diff}")

        if name == "multiedit":
            p     = args.get("path", "?")
            edits = args.get("edits", [])
            lines = [f"{YELLOW}Edit file:{R} {BOLD}{p}{R}  {DIM}({len(edits)} change(s)){R}"]
            for i, e in enumerate(edits[:5], 1):  # show max 5
                diff = _format_diff(e.get("old_str",""), e.get("new_str",""), context=1)
                lines.append(f"  {DIM}[{i}]{R} {diff}")
            if len(edits) > 5:
                lines.append(f"  {DIM}... +{len(edits)-5} more{R}")
            return "\n".join(lines)

        if name == "apply_patch":
            p = args.get("path", "?")
            patch_preview = args.get("patch","")[:400]
            # Colour the patch lines directly
            coloured = []
            for ln in patch_preview.splitlines():
                if ln.startswith("-") and not ln.startswith("---"):
                    coloured.append(f"{RED}{ln}{R}")
                elif ln.startswith("+") and not ln.startswith("+++"):
                    coloured.append(f"{GREEN}{ln}{R}")
                elif ln.startswith("@@"):
                    coloured.append(f"{CYAN}{ln}{R}")
                else:
                    coloured.append(f"{DIM}{ln}{R}")
            return (f"{YELLOW}Apply patch to:{R} {BOLD}{p}{R}\n"
                    + "\n".join(coloured))

        if name == "glob":
            return f"{YELLOW}Find files:{R} {BOLD}{args.get('pattern','?')}{R}  in {args.get('cwd', 'cwd')}"

        if name == "grep":
            return (f"{YELLOW}Search:{R} {BOLD}{args.get('pattern','?')}{R}"
                    f"  in {args.get('path', 'cwd')}"
                    f"  {DIM}(glob: {args.get('glob','*')}){R}")

        if name == "webfetch":
            return f"{YELLOW}Fetch URL:{R} {BOLD}{args.get('url','?')}{R}"

        if name == "websearch":
            return f"{YELLOW}Web search:{R} {BOLD}{args.get('query','?')}{R}"

        if name == "task":
            return f"{YELLOW}Spawn subagent:{R} {BOLD}{args.get('description','?')[:120]}{R}"

        if name.startswith("mcp__"):
            parts = name.split("__", 2)
            server   = parts[1] if len(parts) > 1 else "?"
            mcp_tool = parts[2] if len(parts) > 2 else "?"
            preview  = json.dumps(args, ensure_ascii=False)[:200]
            return (f"{YELLOW}MCP call:{R} {BOLD}{server}.{mcp_tool}{R}\n"
                    f"  {DIM}{preview}{R}")

    except Exception:
        pass  # fallback below

    # Generic fallback
    preview = json.dumps(args, ensure_ascii=False, indent=2)
    if len(preview) > 400:
        preview = preview[:397] + "..."
    return f"{YELLOW}Tool:{R} {BOLD}{name}{R}\n{DIM}{preview}{R}"

def _sandbox_resolve_read(path: str) -> str:
    """Auto-redirect relative/outside path vào sandbox nếu file tồn tại ở đó."""
    if _project_dir is None:
        return path
    # C13 FIX: khi sandbox còn là placeholder (chưa có write đầu tiên),
    # KHÔNG redirect — _resolve_to_sandbox() sẽ gọi _ensure_project_dir()
    # và flip is_placeholder=False chỉ vì AI glob/grep.
    if _project_dir_is_placeholder:
        return path
    p = Path(path).expanduser()
    try:
        p.resolve().relative_to(_project_dir.resolve())
        return path  # đã trong sandbox
    except ValueError:
        sandbox_p = _resolve_to_sandbox(path)
        if sandbox_p.exists():
            return str(sandbox_p)
    return path

def tool_glob(pattern, cwd=None):
    base_str = str(Path(cwd).expanduser()) if cwd else str(Path.cwd())
    base_str = _sandbox_resolve_read(base_str)
    base = Path(base_str)
    err = _check_sandbox_read(str(base))
    if err: return err
    # FIX (bug #3): _check_sandbox_read() chỉ kiểm tra `base` (root tìm kiếm),
    # KHÔNG kiểm tra từng kết quả match sau khi `pattern` được áp dụng. Nếu
    # pattern chứa "../" (vd "../other_session/*.py"), kết quả có thể nằm
    # NGOÀI sandbox dù base hợp lệ — lộ tên/đường dẫn file của session khác.
    # Giải pháp: resolve `base` một lần, rồi lọc lại từng match để đảm bảo nó
    # thực sự nằm trong base sau khi resolve (chặn mọi dạng "..").
    base_resolved = base.resolve()
    def _inside_base(m: Path) -> bool:
        try:
            m.resolve().relative_to(base_resolved)
            return True
        except ValueError:
            return False
    # Try fd (fast, respects .gitignore) then fall back to Python glob
    fd_error = None  # lưu lý do fd fail để không nuốt im lặng
    if shutil.which("fd"):
        try:
            r = subprocess.run(
                ["fd", "--glob", pattern, "--base-directory", str(base),
                 "--exclude", FW_DATA_NAME, "--exclude", "fw.py"],
                capture_output=True, text=True, timeout=10)
            # fd exit code: 0 = OK (có hoặc không có match), 1 = lỗi thật
            # (base-directory không tồn tại, pattern glob không hợp lệ...)
            if r.returncode == 0:
                out = r.stdout.strip()
                lines = [l for l in out.splitlines() if l.strip() not in ("fw.py", "./fw.py")]
                # FIX (bug #3): fd cũng có thể trả về path "../..." nếu pattern
                # chứa traversal — lọc lại từng dòng theo base_resolved.
                lines = [l for l in lines if _inside_base(base / l)]
                return "\n".join(lines) or "(no matches)"
            fd_error = f"fd exit {r.returncode}: {r.stderr.strip()[:300]}"
        except Exception as e:
            fd_error = f"fd {type(e).__name__}: {e}"
    try:
        matches = sorted(base.glob(pattern))
        # Lọc bỏ .fw_data và fw.py — không bao giờ xuất hiện trong kết quả
        matches = [m for m in matches
                   if FW_DATA_NAME not in m.parts
                   and not (m.parent == base and m.name == "fw.py")
                   and _inside_base(m)]
        return "\n".join(str(m.relative_to(base)) for m in matches[:300]) or "(no matches)"
    except Exception as e:
        if fd_error:
            return f"[error: {e} | fd also failed: {fd_error}]"
        return f"[error: {e}]"

def tool_grep(pattern, path=None, glob=None):
    base = _sandbox_resolve_read(path or str(Path.cwd()))
    err = _check_sandbox_read(base)
    if err: return err
    rg_errors = []  # lưu lý do rg fail để không nuốt im lặng nếu grep cũng fail

    # Prefer ripgrep (respects .gitignore, much faster)
    rg = shutil.which("rg") or shutil.which("ripgrep")
    if rg:
        try:
            cmd = [rg, "--line-number", "--no-heading", "--color=never", "--smart-case",
                   "--glob", f"!{FW_DATA_NAME}/**",   # ẩn .fw_data
                   "--glob", "!fw.py"]                 # ẩn fw.py
            if glob: cmd += ["--glob", glob]
            cmd += [pattern, base]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            # rg exit code: 0 = có match, 1 = không match (hợp lệ), 2+ = lỗi thật
            # (pattern regex sai, glob sai, path không tồn tại...)
            if r.returncode in (0, 1):
                return r.stdout.strip() or "(no matches)"
            rg_errors.append(f"rg exit {r.returncode}: {r.stderr.strip()[:300]}")
        except Exception as e:
            rg_errors.append(f"rg {type(e).__name__}: {e}")

    # Fallback to grep
    try:
        cmd = ["grep", "-rn", "--color=never",
               f"--exclude-dir={FW_DATA_NAME}",       # ẩn .fw_data
               "--exclude=fw.py"]                       # ẩn fw.py
        if glob: cmd += [f"--include={glob}"]
        cmd += [pattern, base]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        # grep exit code: 0 = match, 1 = không match (hợp lệ), 2+ = lỗi thật
        if r.returncode in (0, 1):
            return r.stdout.strip() or "(no matches)"
        err_msg = f"grep exit {r.returncode}: {r.stderr.strip()[:300]}"
        if rg_errors:
            err_msg = f"[error: {err_msg} | rg also failed: {'; '.join(rg_errors)}]"
        else:
            err_msg = f"[error: {err_msg}]"
        return err_msg
    except Exception as e:
        if rg_errors:
            return f"[error: grep {type(e).__name__}: {e} | rg also failed: {'; '.join(rg_errors)}]"
        return f"[error: {e}]"


def tool_view_symbol(path, symbol):
    """
    Tìm function/class/method theo tên, trả về đúng block đó.
    Không cần đọc full file — tiết kiệm token tối đa.
    Hỗ trợ: Python, JS/TS, Java, Go, Rust, PHP, Ruby, C/C++
    """
    # Auto-resolve vào sandbox chỉ khi sandbox đã enforce (không phải placeholder)
    # — đồng bộ với tool_read, tránh side-effect tự enforce sandbox sớm.
    if _project_dir is not None and not _project_dir_is_placeholder:
        resolved_p = Path(path).expanduser()
        try:
            resolved_p.resolve().relative_to(_project_dir.resolve())
        except ValueError:
            sandbox_p = _resolve_to_sandbox(path)
            if sandbox_p.exists():
                path = str(sandbox_p)
    err = _check_sandbox_read(path)
    if err: return err
    p = Path(path).expanduser()
    if not p.exists():
        return f"[not found: {path}]"
    try:
        lines = p.read_text(errors="replace").splitlines()
    except Exception as e:
        return f"[error: {e}]"

    # Patterns tìm định nghĩa symbol theo ngôn ngữ
    patterns = [
        # Python: def foo / async def foo / class Foo
        rf"^\s*(async\s+)?def\s+{re.escape(symbol)}\s*[\(:]",
        rf"^\s*class\s+{re.escape(symbol)}\s*[\(:]",
        # JS/TS: function foo / const foo = / foo = function / foo: function / foo() {
        rf"^\s*(export\s+)?(default\s+)?(async\s+)?function\s+{re.escape(symbol)}\s*[\({{]",
        rf"^\s*(export\s+)?(const|let|var)\s+{re.escape(symbol)}\s*=\s*(async\s+)?(\(|function)",
        rf"^\s*{re.escape(symbol)}\s*[:=]\s*(async\s+)?(\(|function)",
        rf"^\s*(export\s+)?(default\s+)?class\s+{re.escape(symbol)}\s*[{{(]",
        # Go: func foo / func (r Recv) foo
        rf"^\s*func\s+(\(\w+\s+\*?\w+\)\s+)?{re.escape(symbol)}\s*\(",
        # Rust: fn foo / pub fn foo
        rf"^\s*(pub\s+)?(async\s+)?fn\s+{re.escape(symbol)}\s*[\(<]",
        # Java/C#: visibility type foo(
        rf"^\s*(public|private|protected|static|override).*\s{re.escape(symbol)}\s*\(",
        # Ruby: def foo
        rf"^\s*def\s+{re.escape(symbol)}\s*[\(\n]",
        # C/C++: returntype foo(
        rf"^\w[\w\s\*]+\s{re.escape(symbol)}\s*\(",
    ]

    # Tìm dòng bắt đầu
    start_line = None
    for i, line in enumerate(lines):
        for pat in patterns:
            if re.search(pat, line):
                start_line = i
                break
        if start_line is not None:
            break

    if start_line is None:
        # Fallback: tìm bất kỳ dòng nào chứa symbol
        for i, line in enumerate(lines):
            if re.search(rf"\b{re.escape(symbol)}\b", line):
                start_line = i
                break

    if start_line is None:
        return f"[symbol '{symbol}' not found in {path}]"

    # Tìm dòng kết thúc block — dựa vào indent hoặc brace counting
    ext = p.suffix.lower()
    end_line = start_line

    if ext in (".py",):
        # Python: dùng indent
        base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
        i = start_line + 1
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "":
                i += 1
                continue
            cur_indent = len(lines[i]) - len(lines[i].lstrip())
            if cur_indent <= base_indent and stripped:
                break
            end_line = i
            i += 1
    else:
        # Brace-based: đếm { }
        depth = 0
        found_open = False
        i = start_line
        while i < len(lines) and i < start_line + 300:
            for ch in lines[i]:
                if ch == "{":
                    depth += 1
                    found_open = True
                elif ch == "}":
                    depth -= 1
            end_line = i
            if found_open and depth <= 0:
                break
            i += 1

    # Clamp: max 120 dòng để không spam token
    if end_line - start_line > 120:
        end_line = start_line + 120
        truncated = True
    else:
        truncated = False

    # Context ±3 dòng
    ctx_start = max(0, start_line - 3)
    ctx_end   = min(len(lines) - 1, end_line + 3)

    out  = f"File: {p}  |  Symbol: `{symbol}`  |  Lines {start_line+1}-{end_line+1} of {len(lines)}\n"
    out += "─" * 60 + "\n"
    out += "\n".join(f"{ctx_start+1+i}\t{l}" for i, l in enumerate(lines[ctx_start:ctx_end+1]))
    if truncated:
        out += f"\n\n... (symbol truncated at 120 lines — use read(offset={end_line+1}) for rest)"
    out += f"\n\nNOTE: Line numbers are display-only. For edit old_str, use ONLY the text after the tab."

    # Track read time
    _file_read_time[str(p.resolve())] = time.time()
    # Cache full file content khi view_symbol (đã đọc toàn bộ lines rồi)
    _cache_put(str(p), "\n".join(lines), _current_sid)
    return out


# Các tag không mang nội dung đọc được — xóa cả tag lẫn nội dung bên trong.
# (script/style: code, không phải text. nav/header/footer/aside: chrome trang,
#  không phải nội dung chính. noscript: fallback cho JS tắt, thường trùng lặp.)
_WEBFETCH_STRIP_TAGS = (
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "svg", "form", "iframe", "button",
)

# Nếu trang có vùng nội dung chính rõ ràng, ưu tiên trích riêng vùng đó
# thay vì toàn bộ <body> (tránh menu/sidebar lẫn vào phần đầu kết quả).
_WEBFETCH_MAIN_TAGS = ("main", "article")

def tool_webfetch(url):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw_bytes = resp.read()

        # Không phải HTML/text (pdf, image, binary...) — báo rõ thay vì trả rác nhị phân.
        if ctype and not any(t in ctype for t in ("text/html", "text/plain", "application/xhtml", "xml")):
            return f"[error: unsupported content-type '{ctype}', cannot extract text]"

        raw = raw_bytes.decode("utf-8", errors="replace")

        # 1) Xóa toàn bộ tag không phải nội dung, kèm nội dung bên trong.
        for tag in ("title",) + _WEBFETCH_STRIP_TAGS:
            raw = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", raw, flags=re.DOTALL | re.IGNORECASE)

        # 2) Nếu có <main> hoặc <article>, ưu tiên lấy nội dung trong đó
        #    (thường là phần bài viết/nội dung chính, ít rác menu/sidebar hơn).
        for tag in _WEBFETCH_MAIN_TAGS:
            m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", raw, flags=re.DOTALL | re.IGNORECASE)
            if m and len(m.group(1)) > 200:  # tránh match nhầm <main> rỗng/quá ngắn
                raw = m.group(1)
                break

        # 3) Giữ lại cấu trúc heading cơ bản dạng markdown trước khi xóa tag,
        #    để output không bị dính hết thành 1 khối văn xuôi.
        raw = re.sub(r"<h1\b[^>]*>(.*?)</h1>", r"\n\n# \1\n", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r"<h2\b[^>]*>(.*?)</h2>", r"\n\n## \1\n", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r"<h3\b[^>]*>(.*?)</h3>", r"\n\n### \1\n", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r"<li\b[^>]*>(.*?)</li>", r"\n- \1", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(r"</p>|<br\s*/?>", "\n", raw, flags=re.IGNORECASE)

        # 4) Xóa tag còn lại (giữ text bên trong), decode HTML entity (&amp; &#39; ...).
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = _html.unescape(raw)

        # 5) Gộp khoảng trắng/dòng trống thừa.
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
        raw = raw.strip()

        if not raw:
            return "[error: no extractable text content found on page]"

        LIMIT = 10000
        if len(raw) > LIMIT:
            raw = raw[:LIMIT] + f"\n\n... [truncated, {len(raw) - LIMIT} more chars — refine query or fetch specific section]"
        return raw
    except urllib.error.HTTPError as e:
        return f"[error: HTTP {e.code} {e.reason}]"
    except urllib.error.URLError as e:
        return f"[error: {e.reason}]"
    except Exception as e:
        return f"[error: {e}]"

def tool_websearch(query, num=5):
    """SearXNG HTML scrape (multi-instance fallback) — fallback to DuckDuckGo HTML scrape."""
    import urllib.parse
    errors = []  # thu thập lỗi từng nhánh để debug khi cả 2 fail

    # ── Nhánh 1: SearXNG public instances — scrape HTML ──────────────────────
    # JSON API bị tắt trên hầu hết public instance nên scrape HTML.
    # Thử từng instance theo thứ tự, dùng kết quả đầu tiên thành công.
    # Instance list từ pwilkin/mcp-searxng-public (uptime tốt, verified 2025).
    _SEARXNG_INSTANCES = [
        "https://metacat.online",
        "https://nyc1.sx.ggtyler.dev",
        "https://ooglester.com",
        "https://search.080609.xyz",
        "https://search.canine.tools",
        "https://search.catboy.house",
        "https://search.im-in.space",
        "https://search.indst.eu",
    ]
    _SEARXNG_UA = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    q_enc = urllib.parse.quote_plus(query)

    for base in _SEARXNG_INSTANCES:
        try:
            url = f"{base}/search?q={q_enc}&language=en&safesearch=0"
            req = urllib.request.Request(url, headers={
                "User-Agent": _SEARXNG_UA,
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            results = []
            seen_urls = set()

            # SearXNG HTML markup: <article class="result"> chứa
            # <h3><a href="...">title</a></h3> và <p class="content">snippet</p>
            for m in re.finditer(
                r'<article[^>]+class="[^"]*result[^"]*"[^>]*>.*?'
                r'<h3[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>.*?</h3>'
                r'(?:.*?<p[^>]+class="[^"]*content[^"]*"[^>]*>(.*?)</p>)?',
                html, re.DOTALL
            ):
                url_r   = m.group(1)
                title   = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                snippet = re.sub(r"<[^>]+>", "", m.group(3) or "").strip()[:250]
                if url_r not in seen_urls and title:
                    seen_urls.add(url_r)
                    results.append(f"**{title}**\n{url_r}\n{snippet}" if snippet
                                   else f"**{title}**\n{url_r}")
                if len(results) >= int(num):
                    break

            # Fallback pattern nếu markup khác: tìm link h3 trực tiếp
            if not results:
                for m in re.finditer(
                    r'<h3[^>]*>.*?<a[^>]+href="(https?://[^"#][^"]+)"[^>]*>(.*?)</a>',
                    html, re.DOTALL
                ):
                    url_r = m.group(1)
                    title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                    if url_r not in seen_urls and title and len(title) > 5:
                        seen_urls.add(url_r)
                        results.append(f"**{title}**\n{url_r}")
                    if len(results) >= int(num):
                        break

            if results:
                return "\n\n".join(results)
            errors.append(f"SearXNG {base}: HTML ok ({len(html)}b) nhưng không parse được")
        except Exception as e:
            errors.append(f"SearXNG {base}: {type(e).__name__}: {e}")
            continue

    # ── Nhánh 2: DuckDuckGo HTML scrape ──────────────────────────────────────
    # Scrape html.duckduckgo.com — không cần API key, không JS.
    # DDG thay đổi markup theo thời gian — thử nhiều pattern theo thứ tự:
    #   Pattern A: class="result__a" + class="result__snippet" (markup cũ)
    #   Pattern B: data-testid hoặc class chứa "result" (markup mới hơn)
    #   Pattern C: extract từ uddg= redirect link (robust hơn, ít bị break)
    # Fail hoặc 0 kết quả → trả "(no results)" kèm debug info.
    try:
        q   = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        req = urllib.request.Request(url, headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []
        seen_urls = set()

        # Pattern A: markup cũ — result__a + result__snippet
        for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>',
            html, re.DOTALL
        ):
            url_r   = urllib.parse.unquote(m.group(1))
            title   = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if url_r not in seen_urls and url_r.startswith("http"):
                seen_urls.add(url_r)
                results.append(f"**{title}**\n{url_r}\n{snippet}")
            if len(results) >= int(num):
                break

        # Pattern B: markup mới — block result giới hạn 2000 chars tránh greedy
        if not results:
            for m in re.finditer(
                r'<(?:h2|h3)[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>'
                r'(.*?)</a>.*?</(?:h2|h3)>(.{0,500}?)'
                r'(?=<(?:h2|h3)|<div[^>]+class="result|$)',
                html, re.DOTALL
            ):
                url_r   = m.group(1)
                title   = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()[:200]
                if url_r not in seen_urls and title:
                    seen_urls.add(url_r)
                    results.append(f"**{title}**\n{url_r}\n{snippet}")
                if len(results) >= int(num):
                    break

        # Pattern C: uddg= redirect links — robust nhất khi markup thay đổi
        # Lọc bỏ link nội bộ DDG (footer/help/about/privacy/ads) — đây là
        # nguyên nhân gây ra kết quả rác kiểu "ads-by-microsoft" thay vì
        # kết quả tìm kiếm thật.
        _DDG_JUNK_HOSTS = (
            "duckduckgo.com",  # help pages, about, privacy, company/...
        )
        def _is_junk_result(url_r: str) -> bool:
            try:
                host = urllib.parse.urlparse(url_r).netloc.lower()
            except Exception:
                return False
            return any(host == h or host.endswith("." + h) for h in _DDG_JUNK_HOSTS)

        if not results:
            for m in re.finditer(
                r'>([^<]{5,80})</[^>]+>\s*(?:<[^>]+>\s*)*'
                r'<a[^>]+uddg=(https?%3A%2F%2F[^&"]+)',
                html
            ):
                title = m.group(1).strip()
                url_r = urllib.parse.unquote(m.group(2))
                if url_r not in seen_urls and not _is_junk_result(url_r):
                    seen_urls.add(url_r)
                    results.append(f"**{title}**\n{url_r}")
                if len(results) >= int(num):
                    break
            # fallback: chỉ URL nếu vẫn không có title
            if not results:
                for m in re.finditer(r'uddg=(https?%3A%2F%2F[^&"]+)', html):
                    url_r = urllib.parse.unquote(m.group(1))
                    if url_r not in seen_urls and not _is_junk_result(url_r):
                        seen_urls.add(url_r)
                        results.append(url_r)
                    if len(results) >= int(num):
                        break

        if results:
            return "\n\n".join(results)
        errors.append(f"DDG: HTML ok ({len(html)} bytes) nhưng regex không match")
    except Exception as e:
        errors.append(f"DDG: {e}")

    # Cả 2 nhánh fail — trả debug info để biết nguyên nhân
    debug = " | ".join(errors) if errors else "unknown"
    return f"(no results for: {query}) [debug: {debug}]"

# Global todo state per session (in-memory, backed by DB)
_todos: list = []
_todos_sid: str = ""
_todos_conn = None
_todowrite_calls_this_turn: int = 0  # hard limit: reset mỗi agent_turn
_large_read_credits: int = 0  # số lần còn được đọc 500 dòng sau khi user y

# FileTime tracking: {resolved_path: timestamp} — ensures AI reads before editing
_file_read_time: dict = {}
_recent_writes: set = set()  # block read-after-write waste; reset mỗi agent_turn



def _todos_init(conn, sid):
    global _todos, _todos_sid, _todos_conn
    _todos_sid  = sid
    _todos_conn = conn
    _todos      = todos_load(conn, sid)

def tool_todowrite(todos):
    global _todos, _todowrite_calls_this_turn
    if _todowrite_calls_this_turn >= 1:
        return "todowrite skipped (limit 1/turn reached — batch updates at major milestones only)"
    _todowrite_calls_this_turn += 1
    _todos = todos
    todos_save(_todos_conn, _todos_sid, todos)
    # BUG ĐÃ SỬA: print() trần ngay trong hàm tool, tách biệt hoàn toàn
    # khỏi run_tool()/EventBus (08_undo_dispatch.py) -- vì thế nội dung chi
    # tiết todo list (icon/priority/status từng item) chỉ hiện trên CLI
    # thật, không bao giờ tới web (không đi qua state.emit nào cả), đúng
    # hiện tượng "lọt ra CLI, không hiện bên web UI" quan sát được. Sửa:
    # dùng current_state() (thread-local, set sẵn ở đầu agent_turn -- xem
    # 01d_events.py, cùng pattern _check_permission() đã dùng) để emit qua
    # EV_INFO khi có state, giữ nguyên print() y hệt cũ khi không có state
    # (CLI chạy ngoài agent_turn, hiếm).
    lines = [f"\n{BOLD}📋 Todo list:{R}"]
    for t in todos:
        icon = {"pending":"○","in_progress":"◉","completed":"✓"}.get(t["status"],"○")
        pri  = {"high":RED,"medium":YELLOW,"low":DIM}.get(t["priority"],DIM)
        lines.append(f"  {pri}{icon}{R} [{t['id']}] {t['content']} {DIM}({t['status']}){R}")
    text = "\n".join(lines)
    _st = current_state()
    if _st is not None:
        _st.emit(EV_INFO, text=text, raw=True)
    else:
        print(text)
    return f"Todo list updated ({len(todos)} items)"

def tool_todoread():
    if not _todos:
        return "(no todos)"
    lines = []
    for t in _todos:
        lines.append(f"[{t['id']}] {t['status']} | {t['priority']} | {t['content']}")
    return "\n".join(lines)

def tool_question(question, options=None, state=None):
    """AI hỏi user — hỗ trợ options list (opencode-style).
    BUG FIX: trước đây hàm này luôn dùng input()/print() thẳng ra CLI, kể cả
    khi đang chạy /web — vì dispatch không truyền `state` xuống đây, khác
    với các tool khác (bash permission-ask, tool_write...) đã đi đúng qua
    state.ask()/state.emit(). Hậu quả: câu hỏi "AI hỏi" luôn rơi vào cửa sổ
    CLI phía sau thay vì hiện trong web UI như ảnh chụp báo lỗi. Sửa theo
    đúng pattern permission-ask ở 08_undo_dispatch.py (dòng ~413-422): có
    state -> emit EV_ASK qua state.ask() (web trả lời qua WS, CLI listener
    vẫn nhận được nếu còn subscribe); không có state (gọi tool trực tiếp
    ngoài luồng agent, hiếm) -> giữ nguyên input() cũ.
    """
    if state is not None:
        if options and isinstance(options, list):
            options = [o.strip() for o in options if isinstance(o, str) and o.strip()]
        if options:
            ans = state.ask(
                prompt=question,
                kind="choice",
                default=options[0] if options else None,
                extra={"options": options},
            )
        else:
            ans = state.ask(prompt=question, kind="text", default=None)
        ans = (ans or "").strip()
        return ans if ans else "(no answer)"

    print(f"\n{BOLD}{BLUE}❓ AI hỏi:{R} {question}")
    # B7 FIX: model đôi khi generate options toàn chuỗi rỗng (vd ["", "", "", ""])
    # — đã thấy thật trong session live, ra menu "1. 2. 3. 4." không có nội dung
    # để chọn. Lọc bỏ option rỗng/chỉ-khoảng-trắng trước khi hiển thị; nếu lọc
    # xong không còn gì, coi như không có options (rơi về free-form input).
    if options and isinstance(options, list):
        options = [o.strip() for o in options if isinstance(o, str) and o.strip()]
    if options and isinstance(options, list) and len(options) > 0:
        for i, opt in enumerate(options, 1):
            print(f"  {YELLOW}{i}.{R} {opt}")
        print(f"  {DIM}(nhập số hoặc gõ tự do){R}")
        try:
            raw = input(f"{CYAN}Chọn: {R}").strip()
        except (EOFError, KeyboardInterrupt):
            return "(user did not answer)"
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]  # đã lọc rỗng ở trên, option[idx] luôn có nội dung
        return raw if raw else "(no answer)"
    try:
        answer = input(f"{CYAN}Trả lời: {R}").strip()
        return answer if answer else "(no answer)"
    except (EOFError, KeyboardInterrupt):
        return "(user did not answer)"

def tool_skill(name):
    """Load a SKILL.md file by name from known skills directories."""
    # Normalise: strip .md suffix, try variations
    candidates = [name, name + ".md", name + "/SKILL.md",
                  name.upper() + "/SKILL.md", f"{name}.skill.md"]
    for skills_dir in SKILLS_DIRS:
        skills_dir_resolved = skills_dir.resolve()
        for c in candidates:
            p = skills_dir / c
            # Path traversal guard: "name" đến từ model, chưa được tin cậy.
            # Path./ không chặn ".." — nếu name="../../../secret/SKILL.md",
            # p sẽ thoát khỏi skills_dir hoàn toàn. Trước đây không có bước
            # này nên tool_skill là tool đọc file DUY NHẤT trong toàn bộ
            # TOOLS thiếu sandbox check (mọi tool khác đều gọi
            # _check_sandbox_read hoặc tương đương). Xác nhận bằng exploit
            # thật: tool_skill("../../../secret_skill_test") đọc được file
            # ngoài SKILLS_DIRS. Giờ chặn bằng cách kiểm tra path đã resolve
            # còn nằm trong skills_dir hay không, cùng pattern _inside_base()
            # đã dùng ở tool_glob.
            try:
                p.resolve().relative_to(skills_dir_resolved)
            except ValueError:
                continue  # thoát khỏi skills_dir — bỏ qua candidate này
            if p.exists() and p.is_file():
                try:
                    content = p.read_text()
                    print(f"  {DIM}[skill] Loaded: {p}{R}")
                    return content
                except Exception as e:
                    return f"[error reading skill: {e}]"
    # List available skills
    available = []
    for sd in SKILLS_DIRS:
        if sd.exists():
            for f in sd.rglob("*.md"):
                # Skill dạng thư mục (name/SKILL.md) → hiện tên thư mục, không phải "SKILL"
                available.append(f.parent.name if f.stem.upper() == "SKILL" else f.stem)
    hint = f"Available: {', '.join(available)}" if available else f"No skills found in {SKILLS_DIRS}"
    return f"[skill not found: '{name}'. {hint}]"

def tool_verify(path: str, reason: str = "") -> str:
    """Hỏi user có muốn verify file/output không.

    BUG ĐÃ SỬA: hàm này trước đây tự print()/input() thẳng, tách biệt hoàn
    toàn khỏi EventBus/state.ask() -- cùng loại bug đã sửa ở tool_todowrite
    phía trên (xem comment ở đó). Hệ quả quan sát được thật: khi đang /web
    (web_bridge armed, bàn phím CLI thật đã khoá), câu hỏi "⊙ Verify?" vẫn
    chỉ hiện ở CLI thật và chặn input() ở đó -- web không nhận được gì,
    người dùng thao tác trên web không thấy câu hỏi để trả lời.

    Sửa: dùng current_state() (thread-local, cùng pattern _check_permission
    ở 08_undo_dispatch.py) để gọi state.ask(kind="confirm") khi có state --
    cơ chế này đã tự định tuyến đúng nơi cần hỏi (web nếu đang armed, CLI
    nếu không, xem cli_ask_handler/make_web_ask_handler ở 01d_events.py).
    Giữ nguyên print()/input() y hệt cũ khi không có state (hiếm, CLI chạy
    ngoài agent_turn) để không đổi hành vi trường hợp đó.
    """
    reason_str = f" — {reason}" if reason else ""
    _st = current_state()
    if _st is not None:
        ans = _st.ask(
            prompt=f"⊙ Verify {path}{reason_str}? [y/N]",
            kind="confirm",
            default="n",
        ) or "n"
        ans = str(ans).strip().lower()
    else:
        reason_str_cli = f"  {DIM}{reason}{R}" if reason else ""
        print(f"\n{CYAN}⊙ Verify?{R}  {BOLD}{path}{R}{reason_str_cli}")
        try:
            ans = input(f"  {DIM}[y/N]: {R}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "verification skipped"
    if ans in ("y", "yes"):
        # Resolve qua sandbox giống mọi tool khác (write/edit/read/extract...)
        p = _resolve_to_sandbox(path)
        if p.is_dir():
            return tool_read(str(p), depth=2)
        elif p.is_file():
            return tool_read(str(p), limit=30)
        else:
            return f"[verify] not found: {p}"
    return "verification skipped by user"


def tool_lsp(operation, file=None, line=None, character=None, query=None):
    """
    Local LSP — powered by Python ast + regex, no server needed.
    Supported operations:
      documentSymbol  — list all functions/classes with line numbers
      hover           — show signature + docstring at line:char
      definition      — find where a symbol is defined
      references      — find all usages of a symbol
      workspace_symbol— search symbols by name across project
    """
    import ast as _ast

    # ── helpers ──────────────────────────────────────────────────────────────
    def _resolve_lsp_file(path):
        if not path:
            return None, "[lsp] file required"
        p = Path(path).expanduser()
        if _project_dir is not None and not _project_dir_is_placeholder:
            try:
                p.resolve().relative_to(_project_dir.resolve())
            except ValueError:
                sandbox_p = _resolve_to_sandbox(path)
                if sandbox_p.exists():
                    p = sandbox_p
        err = _check_sandbox_read(str(p))
        if err:
            return None, err
        return p, None

    def _read(path):
        p, err = _resolve_lsp_file(path)
        if err:
            return None
        try:
            return p.read_text(errors="replace")
        except Exception as e:
            return None

    def _parse(src):
        try:
            return _ast.parse(src)
        except SyntaxError:
            return None

    def _all_symbols(tree, src_lines):
        """Walk AST → list of {name, kind, line, end_line, col, signature, docstring}"""
        results = []
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                kind = "function"
                # Build signature
                args = node.args
                parts = [a.arg for a in args.args]
                if args.vararg:  parts.append("*" + args.vararg.arg)
                if args.kwarg:   parts.append("**" + args.kwarg.arg)
                sig = f"def {node.name}({', '.join(parts)})"
                doc = _ast.get_docstring(node) or ""
                results.append({
                    "name": node.name, "kind": kind,
                    "line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno),
                    "col": node.col_offset, "signature": sig,
                    "docstring": doc[:120] + ("..." if len(doc) > 120 else "")
                })
            elif isinstance(node, _ast.ClassDef):
                doc = _ast.get_docstring(node) or ""
                bases = ", ".join(
                    (b.id if isinstance(b, _ast.Name) else _ast.unparse(b)) for b in node.bases
                ) if hasattr(_ast, "unparse") else ""
                sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
                results.append({
                    "name": node.name, "kind": "class",
                    "line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno),
                    "col": node.col_offset, "signature": sig,
                    "docstring": doc[:120] + ("..." if len(doc) > 120 else "")
                })
        results.sort(key=lambda x: x["line"])
        return results

    def _symbol_at(symbols, line, character):
        """Find deepest symbol enclosing line:character."""
        best = None
        for s in symbols:
            if s["line"] <= line <= s["end_line"]:
                if best is None or (s["line"] >= best["line"] and s["end_line"] <= best["end_line"]):
                    best = s
        return best

    def _token_at(src_lines, line, character):
        """Extract identifier token at line:character (1-based line)."""
        if line < 1 or line > len(src_lines):
            return ""
        row = src_lines[line - 1]
        col = min(character, len(row) - 1)
        start = col
        while start > 0 and (row[start-1].isalnum() or row[start-1] == "_"):
            start -= 1
        end = col
        while end < len(row) and (row[end].isalnum() or row[end] == "_"):
            end += 1
        return row[start:end]

    # ── documentSymbol ────────────────────────────────────────────────────────
    if operation == "documentSymbol":
        if not file:
            return "[lsp] documentSymbol requires file"
        file_path, err = _resolve_lsp_file(file)
        if err:
            return err
        file = str(file_path)
        src = _read(file)
        if src is None:
            return f"[lsp] Cannot read {file}"
        tree = _parse(src)
        if tree is None:
            # Fallback: regex for non-Python or syntax errors
            lines = src.splitlines()
            out = []
            for i, ln in enumerate(lines, 1):
                s = ln.strip()
                if s.startswith("def ") or s.startswith("async def ") or s.startswith("class "):
                    out.append(f"  {i:4d}  {s[:80]}")
            return f"Symbols in {file} ({len(out)} found):\n" + "\n".join(out) if out else f"[lsp] No symbols found in {file}"
        symbols = _all_symbols(tree, src.splitlines())
        if not symbols:
            return f"[lsp] No symbols found in {file}"
        lines_out = [f"Symbols in {file} ({len(symbols)} total):"]
        for s in symbols:
            indent = "  " if s["kind"] == "function" else ""
            doc_hint = f"  # {s['docstring'][:60]}" if s["docstring"] else ""
            lines_out.append(f"  {s['line']:4d}  {indent}{s['signature']}{doc_hint}")
        return "\n".join(lines_out)

    # ── hover ─────────────────────────────────────────────────────────────────
    if operation == "hover":
        if not file:
            return "[lsp] hover requires file"
        file_path, err = _resolve_lsp_file(file)
        if err:
            return err
        file = str(file_path)
        src = _read(file)
        if src is None:
            return f"[lsp] Cannot read {file}"
        tree = _parse(src)
        ln = int(line or 1)
        col = int(character or 0)
        if tree:
            symbols = _all_symbols(tree, src.splitlines())
            sym = _symbol_at(symbols, ln, col)
            if sym:
                out = f"{sym['signature']}\n  Line {sym['line']}–{sym['end_line']}"
                if sym["docstring"]:
                    out += f"\n  {sym['docstring']}"
                return out
        # Fallback: show ±3 lines around target
        src_lines = src.splitlines()
        start = max(0, ln - 3)
        end   = min(len(src_lines), ln + 3)
        snippet = "\n".join(f"  {start+1+i}  {l}" for i, l in enumerate(src_lines[start:end]))
        return f"Context around line {ln}:\n{snippet}"

    # ── definition ────────────────────────────────────────────────────────────
    if operation == "definition":
        if not file and not query:
            return "[lsp] definition requires file (or query to search by name)"
        name = query
        src_lines = []
        if file:
            file_path, err = _resolve_lsp_file(file)
            if err:
                return err
            file = str(file_path)
            src = _read(file)
            if src is None:
                return f"[lsp] Cannot read {file}"
            src_lines = src.splitlines()
            ln  = int(line or 1)
            col = int(character or 0)
            # Get token under cursor or use query
            name = query or _token_at(src_lines, ln, col)
            if not name:
                return "[lsp] No symbol at cursor"
            tree = _parse(src)
            if tree:
                symbols = _all_symbols(tree, src_lines)
                for s in symbols:
                    if s["name"] == name:
                        snippet = src_lines[s["line"]-1].strip()
                        return f"Definition of `{name}`:\n  {file}:{s['line']}  {snippet}"
        if not name:
            return "[lsp] No symbol at cursor"
        # Grep fallback across project (cũng dùng khi không truyền file).
        # Thử cả "def name" (function/method) lẫn "class name" — trước đây
        # chỉ thử "def" nên không tìm được class definition qua fallback.
        search_root = Path(file).parent.name if file else "."
        result = tool_grep(f"def {name}", search_root or ".")
        if "(no matches)" in result:
            result = tool_grep(f"class {name}", search_root or ".")
        if "(no matches)" not in result:
            return f"Definition of `{name}` (grep):\n{result[:800]}"
        return f"[lsp] Definition of `{name}` not found"

    # ── references ────────────────────────────────────────────────────────────
    if operation == "references":
        if not file and not query:
            return "[lsp] references requires file (or query to search by name)"
        name = query
        if file:
            file_path, err = _resolve_lsp_file(file)
            if err:
                return err
            file = str(file_path)
            src = _read(file)
            if src is None:
                return f"[lsp] Cannot read {file}"
            src_lines = src.splitlines()
            ln  = int(line or 1)
            col = int(character or 0)
            name = query or _token_at(src_lines, ln, col)
        if not name:
            return "[lsp] No symbol at cursor"
        return _workspace_references(name, seed_file=file)

    # ── workspace_symbol ──────────────────────────────────────────────────────
    if operation == "workspace_symbol":
        pattern = query or ""
        if not pattern:
            return "[lsp] workspace_symbol requires query"
        result = tool_grep(f"def {pattern}", ".")
        if "(no matches)" in result:
            result = tool_grep(pattern, ".")
        return result[:1500] if result else "[lsp] No matches"

    return f"[lsp] Unknown operation: {operation}. Supported: documentSymbol, hover, definition, references, workspace_symbol"
