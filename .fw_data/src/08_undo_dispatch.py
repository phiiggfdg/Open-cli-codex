# ── Undo / Redo helpers ───────────────────────────────────────────────────────
def _sync_file_state_after_restore(path: "Path", content: str | None) -> None:
    """Keep cache/read-time consistent after undo/redo mutates disk directly."""
    try:
        resolved = str(path.resolve())
        if content is None:
            _file_cache.pop(resolved, None)
            _file_read_time.pop(resolved, None)
            _recent_writes.discard(resolved)
            return
        _cache_put(str(path), content, _current_sid)
        _file_read_time[resolved] = time.time()
        _recent_writes.add(resolved)
    except Exception:
        pass

def do_undo():
    if not _undo_stack:
        return "Nothing to undo."
    snap = _undo_stack.pop()
    p = Path(snap["path"])
    try:
        if snap["before"] is None:
            p.unlink(missing_ok=True)
            _sync_file_state_after_restore(p, None)
            msg = f"Undo: deleted {snap['path']}"
        else:
            p.write_text(snap["before"])
            _sync_file_state_after_restore(p, snap["before"])
            msg = f"Undo: restored {snap['path']}"
        if _project_dir_conn and snap.get("id"):
            _project_dir_conn.execute(
                "UPDATE file_snapshot SET undone=1 WHERE id=?", (snap["id"],))
            _project_dir_conn.commit()
        snap["undone"] = 1
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
        _sync_file_state_after_restore(p, snap["after"])
        if _project_dir_conn and snap.get("id"):
            _project_dir_conn.execute(
                "UPDATE file_snapshot SET undone=0 WHERE id=?", (snap["id"],))
            _project_dir_conn.commit()
        snap["undone"] = 0
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
                    _undo_stack.append(snapshot_save(
                        conn, sid, str(p.resolve()), before, after))
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
            _undo_stack.append(snapshot_save(
                conn, sid, str(p.resolve()), before, after))
            _redo_stack.clear()
        return f"Patch applied to {path}\n" + _patch_snippet(after, patch)
    except Exception as e:
        return f"[error: {e}]"

def tool_task(description, tools=None, model=None, api_key=None, conn=None, sid=None):
    """
    Subagent: chạy một mini agentic loop độc lập.
    Kết quả trả về là text output của subagent.
    """
    _DEFAULT_SUB_TOOLS = {"bash","read","write","edit","glob","grep","webfetch","websearch","todoread"}
    allowed = set(tools) if tools else _DEFAULT_SUB_TOOLS
    sub_tools = [t for t in get_active_tools() if t["function"]["name"] in allowed]

    # Guard: nếu model truyền `tools` toàn tên không tồn tại (vd ảo giác/gõ sai),
    # sub_tools rỗng nhưng tc_mode="required" ở step 0 (xem dưới) vẫn được set —
    # API (mọi format: OpenAI/Anthropic/Bedrock) từ chối ngay "tool_choice
    # required nhưng tools rỗng" với HTTP 400, subagent fail oan dù lẽ ra việc
    # này chỉ là 1 tham số sai vô hại. Fallback về default tool set thay vì để
    # rỗng — "subagent không tool nào cả" chưa bao giờ là ý định hợp lý.
    if not sub_tools:
        sub_tools = [t for t in get_active_tools() if t["function"]["name"] in _DEFAULT_SUB_TOOLS]

    print(f"\n{BLUE}{BOLD}[subagent]{R} {description[:80]}")

    sub_messages = [{"role":"user","content": description}]
    sub_sys = f"""You are a focused subagent. Complete the given task and return a clear result.
Be concise. Current directory: {os.getcwd()}"""

    # C29 FIX: check _no_temperature() thay vì hardcode temperature=0.3
    # C33 FIX: truyền x-session-affinity header như call_api_stream để Requesty cache hit
    _sub_extra_hdrs = {}
    if sid and _active_provider == "requesty":
        _sub_extra_hdrs["x-session-affinity"] = sid

    def _sub_urlopen(payload, timeout=60):
        # Gọi API non-stream và trả về (text, tool_calls) chuẩn hoá.
        # 3 nhánh parse response, khớp đúng với 3 nhánh request trong _provider_request:
        #
        #   Nhánh 1 — aws_bedrock:
        #     _provider_request → build Converse API request (urlopen_smart)
        #     response format  → Converse JSON (khác OpenAI hoàn toàn)
        #     parse            → parse_converse_response() → (text, tool_calls)
        #     tool_calls       → parse đầy đủ từ block "toolUse" (giống nhánh
        #                        2/3) — subagent Bedrock DÙNG ĐƯỢC tool bình
        #                        thường, không có giới hạn nào ở đây
        #
        #   Nhánh 2 — format_anthropic (custom provider dùng Anthropic Messages API):
        #     _provider_request → build_anthropic_request, dịch payload qua _to_anthropic_payload
        #                         "/chat/completions" → "/messages" tự động
        #     response format  → {"content": [{"type":"text",...}, {"type":"tool_use",...}]}
        #     parse            → extract text + convert tool_use → OpenAI tool_calls format
        #     tool_calls       → list OpenAI-style để loop tool_task xử lý bình thường
        #     sub_messages     → append OpenAI-style; lần gọi sau _to_anthropic_payload convert lại
        #
        #   Nhánh 3 — OpenAI-compat (tất cả provider còn lại):
        #     _provider_request → standard Bearer request
        #     response format  → {"choices": [{"message": {"content":..., "tool_calls":[...]}}]}
        #     parse            → choices[0]["message"] trực tiếp
        #
        # C30 FIX: retry 429/5xx
        # C32 FIX: handle aws_bedrock Converse format (nhánh 1)
        # C3X FIX: handle format_anthropic tool_calls (nhánh 2) — trước chỉ parse text, bỏ tool_use
        _RETRY_CODES_SUB = {429, 500, 502, 503, 504}
        _RETRY_DELAYS_SUB = [2, 5, 10]
        for attempt in range(3):
            req = _provider_request("/chat/completions", api_key, payload,
                                    extra_headers=_sub_extra_hdrs or None)
            try:
                if _active_provider == "aws_bedrock":
                    resp_cm = urlopen_smart(req, api_key, payload, timeout=timeout)
                else:
                    resp_cm = urllib.request.urlopen(req, timeout=timeout)
                with resp_cm as resp:
                    body = json.loads(resp.read())

                    # Nhánh 1: AWS Bedrock — Converse API format
                    if _active_provider == "aws_bedrock":
                        parsed = parse_converse_response(body)
                        return parsed.get("text", ""), parsed.get("tool_calls", [])

                    # Nhánh 2: Anthropic Messages API (custom provider format_anthropic=True)
                    # response: {"content": [{"type":"text","text":"..."},
                    #                        {"type":"tool_use","id":"...","name":"...","input":{}}]}
                    if _prov().get("format_anthropic"):
                        content_blocks = body.get("content", [])
                        text = "".join(
                            b.get("text", "") for b in content_blocks
                            if b.get("type") == "text"
                        )
                        # Convert tool_use → OpenAI tool_calls format
                        # để loop tool_task và _dispatch_tool xử lý bình thường.
                        # sub_messages lưu OpenAI-style; _to_anthropic_payload sẽ
                        # convert lại sang tool_use khi gọi API vòng tiếp theo.
                        tool_calls_sub = []
                        for b in content_blocks:
                            if b.get("type") == "tool_use":
                                tool_calls_sub.append({
                                    "id": b.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": b.get("name", ""),
                                        "arguments": json.dumps(b.get("input", {})),
                                    },
                                })
                        return text, tool_calls_sub

                    # Nhánh 3: OpenAI-compat (tất cả provider còn lại)
                    msg = body["choices"][0]["message"]
                    return msg.get("content", "") or "", msg.get("tool_calls") or []
            except urllib.error.HTTPError as e:
                if e.code in _RETRY_CODES_SUB and attempt < 2:
                    import time as _t
                    wait = _RETRY_DELAYS_SUB[attempt]
                    print(f"  {YELLOW}[subagent] HTTP {e.code} — retry {attempt+1}/2 sau {wait}s...{R}", flush=True)
                    _t.sleep(wait)
                    continue
                raise
        raise RuntimeError("subagent: max retries exceeded")

    steps = 0
    final_text = ""
    while steps < 10:
        # tool_choice="required" chỉ hợp lệ khi có ít nhất 1 tool — nếu sub_tools
        # rỗng (không nên xảy ra sau fallback ở trên, nhưng giữ guard tại đây để
        # không phụ thuộc 1 điểm duy nhất), ép "required" sẽ gây HTTP 400 ở mọi
        # format (OpenAI/Anthropic/Bedrock đều từ chối tool_choice required kèm
        # tools rỗng).
        tc_mode = "required" if (steps == 0 and sub_tools) else "auto"
        payload = {
            "model": model, "messages": [{"role":"system","content":sub_sys}]+sub_messages,
            "tools": sub_tools, "tool_choice": tc_mode,
            "max_tokens": 8192, "stream": False,
        }
        # C29 FIX: không gửi temperature với Claude 4+
        if not _no_temperature(model or ""):
            payload["temperature"] = 0.3

        # FIX (bug #6): trước đây subagent KHÔNG BAO GIỜ gửi field "thinking"
        # dù "/mode on" đang bật cho phiên chính — inconsistency không
        # document (subagent luôn chạy non-thinking âm thầm). Giờ tái dùng
        # đúng cache _thinking_support_get() mà agent chính đã probe sẵn
        # cho cặp (provider, model) này — KHÔNG tự probe mới ở đây (tránh
        # tốn thêm 1 request riêng cho subagent). Nếu model chưa từng được
        # biết là có support thinking (None hoặc False), không gửi gì —
        # giữ nguyên hành vi an toàn cũ, không gây 400/422 cho model lạ.
        if _thinking_mode == "on" and _thinking_support_get(model) is True:
            if _prov().get("format_anthropic") or _active_provider == "aws_bedrock":
                payload["thinking"] = {"type": "enabled", "budget_tokens": 8000}
            else:
                payload["thinking"] = {"type": "enabled"}

        try:
            text, tool_calls = _sub_urlopen(payload)
        except Exception as e:
            return f"[subagent error: {e}]"

        # Retry if step 0 returned no tool calls
        if steps == 0 and not tool_calls and sub_tools:
            try:
                payload2 = dict(payload); payload2["tool_choice"] = "required"
                text2, tool_calls2 = _sub_urlopen(payload2)
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
        # FIX (bug #5): trước đây dùng "for pattern, plevel in perms.items(): ...
        # break" — kết quả phụ thuộc INSERTION ORDER của dict, không phải độ cụ
        # thể của pattern. Ví dụ "/perm mcp__* ask" gõ trước rồi
        # "/perm mcp__github_* deny" gõ sau → vì "mcp__*" đứng trước trong dict,
        # nó luôn match trước và break, khiến rule "deny" cụ thể hơn KHÔNG BAO
        # GIỜ có tác dụng — user tưởng đã deny nhưng vẫn ask/allow. Đảo thứ tự
        # gõ lệnh cho kết quả ngược lại hoàn toàn dù ý định không đổi.
        # Giờ: thu thập TẤT CẢ pattern khớp, chọn pattern có phần literal (loại
        # bỏ ký tự "*") dài nhất — tức cụ thể nhất — bất kể thứ tự nhập.
        best_pattern = None
        best_specificity = -1
        for pattern, plevel in perms.items():
            if "*" in pattern and fnmatch.fnmatch(name, pattern):
                specificity = len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_pattern = pattern
                    level = plevel
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
        if name == "bash":
            explanation += ("\nBash có quyền của tiến trình hiện tại và có thể truy cập "
                            "ngoài project_dir; cwd không phải sandbox bảo mật.")
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
        return result
    if name.startswith("mcp__"):
        # B3 FIX: trước đây return ngay tại đây, bỏ qua _check_permission()
        # hoàn toàn — /perm mcp__server_* deny/ask không có tác dụng gì dù
        # docstring _check_permission đã nói rõ hỗ trợ wildcard cho ca này.
        if not _check_permission(name, args):
            return f"[permission denied: {name}]"
        result = mcp_call_tool(name, args)
        return result
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
