# ── Undo / Redo helpers ───────────────────────────────────────────────────────
def do_undo():
    if not _undo_stack:
        return "Nothing to undo."
    snap = _undo_stack.pop()
    p = Path(snap["path"])
    try:
        if snap["before"] is None:
            p.unlink(missing_ok=True)
            msg = f"Undo: deleted {snap['path']}"
        else:
            p.write_text(snap["before"])
            msg = f"Undo: restored {snap['path']}"
        _redo_stack.append(snap)
        return msg
    except Exception as e:
        return f"[undo error: {e}]"

def do_redo():
    if not _redo_stack:
        return "Nothing to redo."
    snap = _redo_stack.pop()
    p = Path(snap["path"])
    try:
        p.write_text(snap["after"])
        _undo_stack.append(snap)
        return f"Redo: applied {snap['path']}"
    except Exception as e:
        return f"[redo error: {e}]"

def _patch_snippet(after: str, patch: str) -> str:
    """
    Trả về context snippet quanh các hunk đã patch.
    Parse dòng '+N' từ @@ header để biết anchor line trong file sau patch.
    Trả về tối đa 3 hunk, mỗi hunk 5 dòng context — AI không cần read lại để verify.
    """
    lines = after.splitlines()
    total = len(lines)
    hunk_anchors = []
    for m in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch):
        start = int(m.group(1)) - 1          # 0-based
        length = int(m.group(2)) if m.group(2) else 1
        hunk_anchors.append((start, length))
    if not hunk_anchors:
        return ""
    parts = []
    for start, length in hunk_anchors[:3]:   # tối đa 3 hunk
        ctx_start = max(0, start - 2)
        ctx_end   = min(total, start + length + 2)
        snippet = "\n".join(f"{ctx_start+1+i}: {l}"
                            for i, l in enumerate(lines[ctx_start:ctx_end]))
        parts.append(snippet)
    header = f"({total} lines total)"
    return header + "\n" + "\n---\n".join(parts)


def tool_apply_patch(path, patch, conn=None, sid=None):
    """Apply unified diff patch — uses system `patch` if available."""
    p = _resolve_to_sandbox(path)
    if not p.exists(): return f"[not found: {p}]"
    try:
        before = p.read_text()
        # Prefer system patch (more robust)
        if shutil.which("patch"):
            result = subprocess.run(
                ["patch", "--unified", str(p)],
                input=patch, text=True, capture_output=True, timeout=15
            )
            if result.returncode == 0:
                after = p.read_text()
                _file_read_time[str(p.resolve())] = time.time()
                _cache_put(str(p), after, _current_sid)
                if conn and sid:
                    snapshot_save(conn, sid, str(p.resolve()), before, after)
                    _undo_stack.append({"path": str(p.resolve()), "before": before, "after": after})
                    _redo_stack.clear()
                return f"Patch applied to {path}\n" + _patch_snippet(after, patch)
            else:
                return f"[patch error]\n{result.stderr.strip()}"
        # Fallback: manual hunk parser
        original = before.splitlines(keepends=True)
        patched  = list(original)
        lines    = patch.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            if lines[i].startswith("@@"):
                m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[i])
                if not m: i += 1; continue
                i += 1
                removes, adds = [], []
                while i < len(lines) and not lines[i].startswith("@@"):
                    l = lines[i]
                    if l.startswith("-"):   removes.append(l[1:])
                    elif l.startswith("+"): adds.append(l[1:])
                    elif l.startswith(" "): removes.append(l[1:]); adds.append(l[1:])
                    i += 1
                src = "".join(removes); dst = "".join(adds)
                content = "".join(patched)
                if src in content:
                    content = content.replace(src, dst, 1)
                    patched = content.splitlines(keepends=True)
                else:
                    return f"[error: patch hunk not found in file]"
            else:
                i += 1
        after = "".join(patched)
        p.write_text(after)
        _file_read_time[str(p.resolve())] = time.time()
        _cache_put(str(p), after, _current_sid)
        if conn and sid:
            snapshot_save(conn, sid, str(p.resolve()), before, after)
            _undo_stack.append({"path": str(p.resolve()), "before": before, "after": after})
            _redo_stack.clear()
        return f"Patch applied to {path}\n" + _patch_snippet(after, patch)
    except Exception as e:
        return f"[error: {e}]"

def tool_task(description, tools=None, model=None, api_key=None, conn=None, sid=None):
    """
    Subagent: chạy một mini agentic loop độc lập.
    Kết quả trả về là text output của subagent.
    """
    allowed = set(tools) if tools else {"bash","read","write","edit","glob","grep","webfetch","websearch","todoread"}
    sub_tools = [t for t in get_active_tools() if t["function"]["name"] in allowed]

    print(f"\n{BLUE}{BOLD}[subagent]{R} {description[:80]}")

    sub_messages = [{"role":"user","content": description}]
    sub_sys = f"""You are a focused subagent. Complete the given task and return a clear result.
Be concise. Current directory: {os.getcwd()}"""

    steps = 0
    final_text = ""
    while steps < 10:
        tc_mode = "required" if steps == 0 else "auto"
        payload = {
            "model": model, "messages": [{"role":"system","content":sub_sys}]+sub_messages,
            "tools": sub_tools, "tool_choice": tc_mode,
            "max_tokens": 8192, "temperature": 0.3, "stream": False,
        }
        req = _provider_request("/chat/completions", api_key, payload)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body       = json.loads(resp.read())
                msg        = body["choices"][0]["message"]
                text       = msg.get("content","") or ""
                tool_calls = msg.get("tool_calls") or []
        except Exception as e:
            return f"[subagent error: {e}]"

        # Retry if step 0 returned no tool calls
        if steps == 0 and not tool_calls:
            try:
                payload2 = dict(payload); payload2["tool_choice"] = "required"
                req2 = _provider_request("/chat/completions", api_key, payload2)
                with urllib.request.urlopen(req2, timeout=60) as resp2:
                    body2      = json.loads(resp2.read())
                    msg2       = body2["choices"][0]["message"]
                    text2      = msg2.get("content","") or ""
                    tool_calls2 = msg2.get("tool_calls") or []
                if tool_calls2:
                    text, tool_calls = text2, tool_calls2
            except Exception:
                pass

        if text:
            final_text = text
            print(f"  {DIM}[subagent] {text[:100]}...{R}" if len(text)>100 else f"  {DIM}[subagent] {text}{R}")

        if tool_calls:
            # Strip heavy content/patch/new_str khỏi arguments trước khi lưu vào
            # sub_messages — subagent loop ngắn (<=10 step) nhưng KHÔNG đi qua
            # _prune_tool_results, nên nếu giữ full content mỗi step sẽ leak
            # token y như bug 10M token ở main loop, chỉ là phiên bản mini.
            STRIP_TOOLS_SUB = {"write", "multiedit", "apply_patch", "edit"}
            stored_tool_calls = []
            for tc in tool_calls:
                name = tc["function"]["name"]
                if name in STRIP_TOOLS_SUB:
                    try:
                        a = json.loads(tc["function"]["arguments"])
                        placeholder = "[content omitted from history — see tool result below for outcome]"
                        for k in ("content", "patch", "new_str"):
                            if k in a:
                                a[k] = placeholder
                        if "edits" in a:
                            for e in a["edits"]:
                                if "new_str" in e:
                                    e["new_str"] = placeholder
                        tc = {**tc, "function": {**tc["function"], "arguments": json.dumps(a)}}
                    except Exception:
                        pass
                stored_tool_calls.append(tc)
            sub_messages.append({"role":"assistant","content": text or None,
                                  "tool_calls": stored_tool_calls})
            for tc in tool_calls:
                name = tc["function"]["name"]
                try: args = json.loads(tc["function"]["arguments"])
                except: args = {}
                print(f"  {BLUE}[sub:{name}]{R} {DIM}{json.dumps(args)[:80]}{R}")
                out = _dispatch_tool(name, args, model, api_key, conn, sid)
                sub_messages.append({"role":"tool","tool_call_id":tc.get("id",""),
                                      "content": _head_tail(str(out), TOOL_OUTPUT_MAX_CHARS, label=f"sub:{name}")})
        else:
            break
        steps += 1

    return final_text or "(subagent completed with no output)"

# ── Permission check ─────────────────────────────────────────────────────────
_current_agent = AGENT_BUILD
_current_sid: str = ""  # session id hiện tại — set mỗi agent_turn
_custom_perms: dict = {}
_bash_allow_all: bool = False  # set True khi user chọn "a" = allow all bash

def _check_permission(name, args, agent=None):
    """Returns True if tool is allowed. Handles ask/deny/allow + wildcard patterns."""
    ag = agent or _current_agent
    # Merge: custom > plan-override > default
    perms = dict(DEFAULT_PERMS)
    if ag == AGENT_PLAN:
        perms.update(PLAN_PERMS)
    perms.update(_custom_perms)
    # Exact match first, then wildcard (e.g. "mymcp_*": "ask")
    level = perms.get(name)
    if level is None:
        import fnmatch
        for pattern, plevel in perms.items():
            if "*" in pattern and fnmatch.fnmatch(name, pattern):
                level = plevel
                break
    if level is None:
        level = PERM_ALLOW
    if level == PERM_DENY:
        print(f"  {RED}✗ {name} denied (agent={ag}){R}")
        return False
    if level == PERM_ASK:
        global _bash_allow_all
        if _bash_allow_all and name == "bash":
            return True
        print(f"\n  {YELLOW}{'─'*56}{R}")
        explanation = _explain_tool_action(name, args)
        for line in explanation.splitlines():
            print(f"  {line}")
        print(f"  {YELLOW}{'─'*56}{R}")
        try:
            ans = input(f"  {CYAN}Allow? [y/N/a(ll)]: {R}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans in ("a", "all"):
            _bash_allow_all = True
            print(f"  {GREEN}✓ Allow all bash for this session.{R}")
            return True
        if ans not in ("y", "yes"):
            print(f"  {RED}✗ Denied by user.{R}")
            return False
    return True

# ── Dispatch ─────────────────────────────────────────────────────────────────
def _dispatch_tool(name, args, model, api_key, conn, sid):
    if name == "set_tools":
        result = tool_set_tools(args.get("tools", []))
        return result, result
    if name.startswith("mcp__"):
        result = mcp_call_tool(name, args)
        return result, result
    if not _check_permission(name, args):
        return f"[permission denied: {name}]"
    dispatch = {
        "bash":        lambda a: tool_bash(a["command"], a.get("timeout",30)),
        "read":        lambda a: tool_read(a["path"], a.get("offset",1), a.get("limit",READ_DEFAULT_LIMIT), a.get("depth",4)),
        "write":       lambda a: tool_write(a["path"], a["content"], conn, sid),
        "extract":     lambda a: tool_extract(a["src"], a["start"], a["end"], a["dst"], a.get("mode","move"), conn, sid),
        "edit":        lambda a: tool_edit(a["path"], a["old_str"], a["new_str"], conn, sid),
        "multiedit":   lambda a: tool_multiedit(a["path"], a["edits"], conn, sid),
        "glob":        lambda a: tool_glob(a["pattern"], a.get("cwd")),
        "grep":        lambda a: tool_grep(a["pattern"], a.get("path"), a.get("glob")),
        "webfetch":    lambda a: tool_webfetch(a["url"]),
        "websearch":   lambda a: tool_websearch(a["query"], a.get("num",5)),
        "todowrite":   lambda a: tool_todowrite(a["todos"]),
        "todoread":    lambda a: tool_todoread(),
        "question":    lambda a: tool_question(a["question"], a.get("options")),
        "apply_patch": lambda a: tool_apply_patch(a["path"], a["patch"], conn, sid),
        "task":        lambda a: tool_task(a["description"], a.get("tools"),
                                           model, api_key, conn, sid),
        "skill":       lambda a: tool_skill(a["name"]),
        "view_symbol": lambda a: tool_view_symbol(a["path"], a["symbol"]),
        "lsp":         lambda a: tool_lsp(a["operation"], a.get("file"),
                                          a.get("line"), a.get("character"), a.get("query")),
        "file_index":  lambda a: tool_file_index(),
        "verify":      lambda a: tool_verify(a["path"], a.get("reason", "")),
    }
    fn = dispatch.get(name)
    if not fn: return f"[unknown tool: {name}]"
    try:
        return fn(args)
    except KeyError as e:
        return f"[tool_error: missing required arg {e} for tool '{name}'. args received: {list(args.keys())}]"

TOOL_ICONS = {
    "bash":        f"{YELLOW}$",
    "read":        f"{CYAN}📄",
    "write":       f"{GREEN}✎",
    "extract":     f"{GREEN}✂",
    "edit":        f"{GREEN}✎",
    "multiedit":   f"{GREEN}✎",
    "apply_patch": f"{GREEN}⊕",
    "glob":        f"{CYAN}⌕",
    "grep":        f"{CYAN}⌕",
    "webfetch":    f"{BLUE}↓",
    "websearch":   f"{BLUE}⌖",
    "todowrite":   f"{MAGENTA}📋",
    "todoread":    f"{MAGENTA}📋",
    "question":    f"{BLUE}❓",
    "task":        f"{CYAN}⇢",
    "skill":       f"{YELLOW}★",
    "lsp":         f"{DIM}◎",
    "file_index":  f"{MAGENTA}⊞",
    "verify":      f"{CYAN}⊙",
}

def run_tool(name, args, model, api_key, conn, sid):
    icon = TOOL_ICONS.get(name, f"{DIM}⚙")
    preview = json.dumps(args, ensure_ascii=False)[:100]
    print(f"  {icon} {BOLD}{name}{R}  {DIM}{preview}{R}")
    result = _dispatch_tool(name, args, model, api_key, conn, sid)
    brief  = str(result)[:200].replace("\n","↵")
    print(f"  {DIM}╰─ {brief}{'…' if len(str(result))>200 else ''}{R}")
    # Cap what the model sees — head+tail like openai/codex
    result_for_model   = _head_tail(str(result), TOOL_OUTPUT_MAX_CHARS,  label=name)
    # Cap what stays in context history (even smaller — lives forever)
    result_for_history = _head_tail(str(result), TOOL_HISTORY_MAX_CHARS, label=name)
    return result_for_model, result_for_history

# ════════════════════════════════════════════════════════════════════════════
# FIREWORKS API
# ════════════════════════════════════════════════════════════════════════════

