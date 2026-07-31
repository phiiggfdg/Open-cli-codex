# ── Todos ────────────────────────────────────────────────────────────────────
def todos_load(conn, sid):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM todo WHERE session_id=? ORDER BY updated_at", (sid,)).fetchall()]

def todos_save(conn, sid, todos):
    conn.execute("DELETE FROM todo WHERE session_id=?", (sid,))
    now = int(time.time())
    seen_ids = {}
    for t in todos:
        tid = t.get("id") or str(uuid.uuid4())[:8]
        # Dedup: nếu trùng id thì giữ cái sau cùng
        seen_ids[tid] = t
    for tid, t in seen_ids.items():
        conn.execute("INSERT OR REPLACE INTO todo VALUES (?,?,?,?,?,?)",
                     (tid, sid,
                      t["content"], t.get("status","pending"),
                      t.get("priority","medium"), now))
    conn.commit()

# ── File snapshots (undo/redo) ───────────────────────────────────────────────
def snapshot_save(conn, sid, path, before, after):
    # A new edit after undo creates a new history branch; stale redo entries
    # must not become available again after a restart.
    conn.execute("DELETE FROM file_snapshot WHERE session_id=? AND undone=1", (sid,))
    snap = {
        "id": str(uuid.uuid4()), "session_id": sid, "path": path,
        "before": before, "after": after, "created_at": int(time.time()),
        "undone": 0,
    }
    conn.execute("""INSERT INTO file_snapshot
                    (id,session_id,path,before,after,created_at,undone)
                    VALUES (?,?,?,?,?,?,?)""",
                 tuple(snap[k] for k in (
                     "id", "session_id", "path", "before", "after",
                     "created_at", "undone")))
    conn.commit()
    return snap

def snapshots_load(conn, sid):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM file_snapshot WHERE session_id=? ORDER BY created_at, rowid",
        (sid,)).fetchall()]

def undo_state_load(conn, sid):
    """Restore durable undo/redo stacks in their correct pop order."""
    active = [dict(r) for r in conn.execute(
        "SELECT * FROM file_snapshot WHERE session_id=? AND undone=0 "
        "ORDER BY created_at, rowid", (sid,)).fetchall()]
    undone = [dict(r) for r in conn.execute(
        "SELECT * FROM file_snapshot WHERE session_id=? AND undone=1 "
        "ORDER BY created_at DESC, rowid DESC", (sid,)).fetchall()]
    _undo_stack[:] = active
    _redo_stack[:] = undone

# ════════════════════════════════════════════════════════════════════════════
# TOKEN / COMPACT
# ════════════════════════════════════════════════════════════════════════════

def estimate_tokens(messages):
    """Ước lượng số token của messages.

    BUG ĐÃ SỬA: trước đây hàm này json.dumps() thẳng messages GỐC trong RAM
    -- nhưng ảnh base64 của các turn CŨ chỉ bị thay bằng placeholder text
    lúc BUILD PAYLOAD GỌI API (xem _strip_old_images ở 09_api_system.py),
    không phải bị xoá khỏi messages trong RAM. Ảnh base64 gốc (thường
    100-300KB/ảnh) vẫn nằm nguyên trong messages mãi mãi, khiến mỗi lần
    estimate_tokens() chạy đều CỘNG DỒN ước lượng token của MỌI ảnh đã
    từng gửi trong session -- kể cả khi model không còn thấy chúng nữa.
    Kết quả: thanh context bar và cảnh báo compact báo % giả tạo, phình to
    rất nhanh chỉ sau vài lần gửi ảnh (từng thấy 222% dù model thực tế còn
    xa mới đầy) -- dẫn tới hỏi compact/xoá lịch sử không cần thiết.

    Sửa: áp dụng cùng phép strip-ảnh-cũ (_strip_old_images) trước khi ước
    lượng, để con số phản ánh đúng những gì thực sự được gửi lên model ở
    lần gọi API kế tiếp -- khớp với _compact_threshold vốn cũng dựa trên
    context window thật của model.
    """
    try:
        messages = _strip_old_images(messages)
    except NameError:
        # _strip_old_images được định nghĩa ở module load sau (09_api_system.py)
        # nhưng cùng namespace runtime -- nếu vì lý do nào đó chưa sẵn sàng
        # (không nên xảy ra trong luồng chạy bình thường của fw.py), fallback
        # về ước lượng thô cũ thay vì crash.
        pass
    total = 0
    for m in messages:
        total += len(json.dumps(m, ensure_ascii=False)) // CHARS_PER_TOKEN
    return total

COMPACT_PROMPT = """Create a detailed Vietnamese summary of the conversation so far.
This will replace earlier messages to keep context manageable.

Include:
1. Main task/goal
2. Key decisions and rationale
3. Files created/modified/deleted (with paths)
4. Commands run and results
5. Current status and what remains
6. Important errors or constraints

Be thorough. Factual, neutral tone. Use clear sections.
Write in Vietnamese, except for exact commands, file paths, errors, identifiers, and quoted output.
Some messages below were truncated before reaching you. If a path, command, or fact appears to end mid-sentence, mark it as truncated/uncertain instead of completing it from assumption."""

def compact_messages(messages, model, api_key, mode: str = "soft"):
    """
    mode='soft': giữ KEEP_RECENT messages gần nhất, tóm tắt phần còn lại.
    mode='hard': giữ ít hơn (KEEP_RECENT//2), tóm tắt ngắn hơn.
    """
    keep = KEEP_RECENT if mode == "soft" else max(2, KEEP_RECENT // 2)
    if len(messages) <= keep:
        return messages
    old    = messages[:-keep]
    recent = messages[-keep:]
    label  = "nhẹ" if mode == "soft" else "mạnh"
    print(f"\n{YELLOW}[compact/{label}] Tóm tắt {len(old)} messages...{R}")
    hist = ""
    for m in old:
        role = m["role"].upper()
        c    = m.get("content") or ""
        if m.get("tool_calls"):
            tnames = [tc["function"]["name"] for tc in m["tool_calls"]]
            c = f"(called tools: {', '.join(tnames)}) {c or ''}"
        char_limit = 400 if mode == "hard" else 600
        hist += f"\n[{role}]: {json.dumps(str(c), ensure_ascii=False)[:char_limit]}\n"
    detail = "Be concise." if mode == "hard" else ""
    try:
        summary = _call_simple(
            [{"role":"user","content": COMPACT_PROMPT+detail+"\n\n<conversation>"+hist+"</conversation>"}],
            model, api_key).get("text","")
        if not summary:
            raise ValueError("empty summary")
    except Exception as _ce:
        # Fallback: nếu API fail khi compact, giữ nguyên recent messages
        # thay vì crash — tránh mất context hoàn toàn.
        print(f"{RED}[compact/{label}] API lỗi ({_ce}), giữ nguyên {keep} messages gần nhất.{R}")
        return recent
    print(f"{DIM}[compact/{label}] Done. {len(old)} → 1 summary.{R}\n")
    # Không inject cache_block vào summary — nội dung thay đổi mỗi lần phá prefix cache.
    # File context sẽ được re-read bình thường khi AI cần.
    return [
        {"role":"user",      "content": "[SUMMARY OF EARLIER CONVERSATION]\n\n"+summary},
        {"role":"assistant", "content": "Understood. Continuing from summary context."},
    ] + recent

def _compact_threshold(model: str) -> tuple[int, int]:
    """Trả về (soft_threshold, hard_threshold) theo context window của model.
    Ưu tiên: exact match ID → substring match → fallback 128_000.
    context_limits được bổ sung động từ API khi fetch_models (xem _patch_context_limits_from_api).
    """
    limits = _context_limits()
    model_short = model.split("/")[-1].lower()

    # 1. Exact match (ID đầy đủ — do _patch_context_limits_from_api ghi vào)
    if model in limits:
        return int(limits[model] * COMPACT_RATIO_SOFT), int(limits[model] * COMPACT_RATIO_HARD)

    # 2. Substring match (key ghi cứng dạng ngắn, vd "deepseek-v3")
    for key, limit in limits.items():
        if key.lower() in model_short or key.lower() in model.lower():
            return int(limit * COMPACT_RATIO_SOFT), int(limit * COMPACT_RATIO_HARD)

    # 3. Fallback — 128K là context window phổ biến nhất hiện tại
    return int(128_000 * COMPACT_RATIO_SOFT), int(128_000 * COMPACT_RATIO_HARD)

COMPACT_TURN_THRESHOLD = 25  # compact chủ động khi history dài hơn N turns

def maybe_compact(messages, model, api_key, conn, sid):
    soft_thresh, hard_thresh = _compact_threshold(model)
    current = estimate_tokens(messages)

    # ── Token-based compact: chỉ khi gần đầy context, hỏi user trước ──────────
    if current < soft_thresh:
        return messages
    if current >= hard_thresh:
        mode = "hard"
        color = RED
    else:
        mode = "soft"
        color = YELLOW
    pct = int(current / hard_thresh * 100)
    # BUG ĐÃ SỬA: input()/print() trần ở đây vi phạm nguyên tắc event-bus
    # của toàn bộ app (xem comment 10_main.py:704-707 — "KHÔNG còn print()/
    # input() nào chạy khi có state"). maybe_compact() được gọi từ ngay
    # trong agent_turn(), nên khi turn chạy qua /web (bàn phím CLI đã bị
    # khoá bởi WebInputBridge), input() ở đây chặn cứng đọc stdin mà không
    # ai gõ được — turn treo vô thời hạn, không có đường thoát (không đi
    # qua state.ask()/PendingAsk như mọi xác nhận khác trong app).
    # Sửa: dùng current_state()/state.ask(kind="confirm") đúng pattern đã
    # có sẵn (giống /setkey ở 10_main.py, permission-ask ở 08_undo_dispatch.py).
    # Không đổi chữ ký hàm maybe_compact (tránh vỡ mọi lời gọi hiện có) —
    # current_state() là thread-local, đã được set_current_state(state) ở
    # đầu agent_turn() trước khi vòng lặp gọi tới đây, nên luôn có giá trị
    # đúng lúc chạy. Khi không có ask_handler nào (không nên xảy ra trong
    # luồng thực tế vì cli_ask_handler luôn subscribe ở main()), EventBus.ask()
    # tự trả về default="y" ngay, an toàn — khớp hành vi cũ khi input() gặp
    # EOFError/KeyboardInterrupt.
    st = current_state()
    prompt = (f"\n{color}{'─'*56}{R}\n"
              f"  {BOLD}[compact]{R} Context đang ở {pct}% ({current:,} tok).\n"
              f"  {DIM}Cần tóm tắt lịch sử cũ để giải phóng không gian.{R}\n"
              f"  {CYAN}Tóm tắt và xoá các tin nhắn cũ? [Y/n]: {R}")
    if st is not None:
        ans = (st.ask(prompt, kind="confirm", default="y") or "y").strip().lower()
    else:
        # Fallback: không có state nào đang chạy (không nên xảy ra qua
        # agent_turn bình thường) — giữ hành vi input() cũ để không phá
        # vỡ code path nào khác có thể còn gọi maybe_compact() độc lập.
        print(prompt, end="")
        try:
            ans = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "y"
    if ans in ("n", "no", "không", "k"):
        if st is not None:
            st.emit(EV_WARN, text="Bỏ qua compact — context có thể bị tràn.")
        else:
            print(f"  {YELLOW}Bỏ qua compact — context có thể bị tràn.{R}")
        return messages
    if st is not None:
        st.emit(EV_INFO, text=f"[compact/{mode}] Context {current:,} tok ({pct}% of limit)...")
    else:
        print(f"{color}[compact/{mode}] Context {current:,} tok ({pct}% of limit)...{R}")
    c = compact_messages(messages, model, api_key, mode=mode)
    # Chỉ ghi DB nếu compact thực sự xảy ra (tức là c là danh sách summary+recent,
    # không phải `recent` thuần — trường hợp fallback do API lỗi).
    # Phân biệt: compact thành công → c[0]["content"] bắt đầu bằng "[SUMMARY"
    if c is not messages and len(c) > 0 and str(c[0].get("content","")).startswith("[SUMMARY"):
        messages_replace_all(conn, sid, c)
    elif c is not messages:
        # Fallback: API lỗi, compact_messages trả về recent.
        # Không ghi DB để tránh mất message cũ vĩnh viễn — giữ nguyên messages trong RAM.
        pass
    return c

def _context_bar(messages, model: str) -> str:
    """
    Render thanh context: ctx ▓▓▓▓▓░░░░░ 42%  27,420 / 65,000
    Màu: teal < 50%, vàng 50-80%, đỏ > 80%.
    Dùng chung _compact_threshold để đảm bảo exact/substring/fallback nhất quán.
    """
    _, hard_thresh = _compact_threshold(model)
    # hard_thresh = limit * COMPACT_RATIO_HARD → chia ngược ra context window thật
    limit = int(hard_thresh / COMPACT_RATIO_HARD) if COMPACT_RATIO_HARD else 128_000
    current = estimate_tokens(messages)
    pct     = min(current / limit, 1.0) if limit else 0
    filled  = int(pct * 12)
    bar     = "▓" * filled + "░" * (12 - filled)
    pct_int = int(pct * 100)
    if pct_int < 50:
        color = TEAL
    elif pct_int < 80:
        color = YELLOW
    else:
        color = RED
    return (f"{DIM}ctx {R}{color}{bar}{R} "
            f"{color}{pct_int}%{R}  "
            f"{GRAY}{current:,} / {limit:,}{R}")

# ── Session cost accumulator ──────────────────────────────────────────────────
_session_cost_usd: float = 0.0  # tích lũy cả session

def _add_session_cost(cost: float):
    global _session_cost_usd
    _session_cost_usd += cost

def _session_cost_str() -> str:
    if _session_cost_usd < 0.0001:
        return f"{DIM}session $0.0000{R}"
    return f"{DIM}session ${_session_cost_usd:.4f}{R}"

# ════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS  (descriptions từ anomalyco/opencode, MIT)
# ════════════════════════════════════════════════════════════════════════════

TOOLS = [
  {"type":"function","function":{
    "name":"bash",
    "description":"Run one allowlisted shell command for inspect/build/test/git/install. No chaining, pipe, redirect, shell expansion, or inline eval; use file tools for mutations. Output includes exit_code, stderr, error_class, retry_hint.",
    "parameters":{"type":"object","properties":{
      "command":{"type":"string"},
      "timeout":{"type":"integer","description":"Seconds (default 30)"}
    },"required":["command"]}
  }},
  {"type":"function","function":{
    "name":"read",
    "description":"Read file with line numbers or list directory as tree. Output includes an auto-generated Anchor map (functions/classes/CSS rules/headings near your offset) — check it first before grepping again. Prefer a small offset+limit over whole-file reads on large files; see system prompt Discovery policy for the full search order.",
    "parameters":{"type":"object","properties":{
      "path":  {"type":"string"},
      "offset":{"type":"integer","description":"Start line 1-indexed (files only)"},
      "limit": {"type":"integer","description":"Max lines to read. Always pass explicitly. Keep ≤60. Default 60. Never exceed 150."},
      "depth": {"type":"integer","description":"Max tree depth for directories (default 4)"}
    },"required":["path"]}
  }},
  {"type":"function","function":{
    "name":"write",
    "description":"Create a NEW file only. File must NOT exist yet. For existing files, always use edit or multiedit instead.",
    "parameters":{"type":"object","properties":{
      "path":   {"type":"string"},
      "content":{"type":"string"}
    },"required":["path","content"]}
  }},
  {"type":"function","function":{
    "name":"delete",
    "description":"Delete a single existing file (not directories — refuses if path is a directory). Undoable via the same undo/redo stack as write/edit. Use this instead of bash 'rm' — 'rm' is not in the bash allowlist and will be rejected.",
    "parameters":{"type":"object","properties":{
      "path":{"type":"string","description":"Path of the file to delete"}
    },"required":["path"]}
  }},
  {"type":"function","function":{
    "name":"extract",
    "description":"Move or copy a LINE RANGE from one file into another file (appends if dst exists, creates if not) WITHOUT retyping content — use this when splitting/refactoring code into modules. mode='move' (default) removes the range from src after copying; mode='copy' keeps src unchanged. ALWAYS prefer this over read+write when relocating existing code blocks.",
    "parameters":{"type":"object","properties":{
      "src":  {"type":"string","description":"Source file path"},
      "start":{"type":"integer","description":"First line to extract (1-indexed, inclusive)"},
      "end":  {"type":"integer","description":"Last line to extract (1-indexed, inclusive)"},
      "dst":  {"type":"string","description":"Destination file path"},
      "mode": {"type":"string","enum":["move","copy"],"description":"Default 'move' (remove from src). Use 'copy' to keep src unchanged."}
    },"required":["src","start","end","dst"]}
  }},
  {"type":"function","function":{
    "name":"edit",
    "description":"Simple replacement for one precise, single-location change. Not for multiple locations or large sections — see system prompt Editing policy for choosing between edit/multiedit/apply_patch.",
    "parameters":{"type":"object","properties":{
      "path":   {"type":"string"},
      "old_str":{"type":"string","description":"Exact text to find (must be unique in file). Do NOT include line-number prefixes shown by the read tool."},
      "new_str":{"type":"string","description":"Replacement text"}
    },"required":["path","old_str","new_str"]}
  }},
  {"type":"function","function":{
    "name":"multiedit",
    "description":"Multiple targeted replacements in one file, one call. Use when changing 2-5 known locations. Each old_str must be unique. Applied atomically: edits run in order against the file state as it stands after the previous edits in this call, and if ANY edit fails, NONE of them are written - the file is left completely unchanged and you must fix the failing edit and retry the whole call.",
    "parameters":{"type":"object","properties":{
      "path":  {"type":"string"},
      "edits": {"type":"array","description":"List of edits to apply in order","items":{
        "type":"object","properties":{
          "old_str":{"type":"string","description":"Exact text to replace (no line-number prefixes)"},
          "new_str":{"type":"string","description":"Replacement text"}
        },"required":["old_str","new_str"]
      }}
    },"required":["path","edits"]}
  }},
  {"type":"function","function":{
    "name":"apply_patch",
    "description":"Best tool for modifying code efficiently. Use when: changing more than 3 lines, editing multiple locations in one file, or restructuring code. Single call replaces multiple edit calls.",
    "parameters":{"type":"object","properties":{
      "path": {"type":"string","description":"File to patch"},
      "patch":{"type":"string","description":"Unified diff patch (--- a/file, +++ b/file, @@ ... @@ format)"}
    },"required":["path","patch"]}
  }},
  {"type":"function","function":{
    "name":"glob",
    "description":"Find files by glob pattern e.g. '**/*.py'. Returns paths relative to cwd.",
    "parameters":{"type":"object","properties":{
      "pattern":{"type":"string"},
      "cwd":    {"type":"string","description":"Search root (default: current directory)"}
    },"required":["pattern"]}
  }},
  {"type":"function","function":{
    "name":"grep",
    "description":"Search regex in files. Returns file:line:content. Extended regex syntax (\\d, \\w, (a|b), {2,4}, + ?) all supported.",
    "parameters":{"type":"object","properties":{
      "pattern":     {"type":"string","description":"Regex pattern (or literal string if fixed_string=true)"},
      "path":        {"type":"string","description":"File or directory (default: cwd)"},
      "glob":        {"type":"string","description":"Only files matching this glob e.g. '*.py'"},
      "ignore_case": {"type":"boolean","description":"Case-insensitive match (like -i)"},
      "fixed_string":{"type":"boolean","description":"Treat pattern as literal text, not regex (like -F). Use when pattern has unescaped ., (, [, + etc. that should match literally."},
      "invert":      {"type":"boolean","description":"Return lines that do NOT match (like -v)"},
      "word":        {"type":"boolean","description":"Match whole words only (like -w), avoids matching inside longer identifiers"},
      "context":     {"type":"integer","description":"Include N lines of context before/after each match (like -C N)"},
      "max_count":   {"type":"integer","description":"Stop after N matches per file (like -m N), use for broad/common patterns to avoid huge output"},
      "files_only":  {"type":"boolean","description":"Only list file paths that contain a match, not the matching lines (like -l)"},
      "multiline":   {"type":"boolean","description":"Let pattern span multiple lines, e.g. to match a whole block like 'class Foo {...}'. Slower, use only when a single-line grep can't express the match."}
    },"required":["pattern"]}
  }},
  {"type":"function","function":{
    "name":"webfetch",
    "description":"Fetch text content of a URL.",
    "parameters":{"type":"object","properties":{
      "url":{"type":"string"}
    },"required":["url"]}
  }},
  {"type":"function","function":{
    "name":"websearch",
    "description":"Search the web for current info, docs, or errors.",
    "parameters":{"type":"object","properties":{
      "query":{"type":"string","description":"Search query"},
      "num":  {"type":"integer","description":"Number of results (default 5)"}
    },"required":["query"]}
  }},
  {"type":"function","function":{
    "name":"todowrite",
    "description":"Replace the current todo list with a new one. See system prompt Task management policy for when and how often to call this.",
    "parameters":{"type":"object","properties":{
      "todos":{"type":"array","description":"Full list of todos (replaces existing)","items":{
        "type":"object","properties":{
          "id":      {"type":"string","description":"Short unique id e.g. '1','2a'"},
          "content": {"type":"string","description":"Task description"},
          "status":  {"type":"string","enum":["pending","in_progress","completed"]},
          "priority":{"type":"string","enum":["high","medium","low"]}
        },"required":["id","content","status","priority"]
      }}
    },"required":["todos"]}
  }},
  {"type":"function","function":{
    "name":"todoread",
    "description":"Read current todo list. Only call if user explicitly asks to see todos, or if you need to check status before updating.",
    "parameters":{"type":"object","properties":{},"required":[]}
  }},
  {"type":"function","function":{
    "name":"question",
    "description":"Ask user a clarifying question. Provide options when answer is a fixed set. ALWAYS write the question and options in Vietnamese.",
    "parameters":{"type":"object","properties":{
      "question":{"type":"string","description":"The question to ask the user"},
      "options": {"type":"array","items":{"type":"string"},"description":"Optional list of choices for the user to pick from"}
    },"required":["question"]}
  }},

  {"type":"function","function":{
    "name":"task",
    "description":"Spawn subagent for isolated subtask. Only for complex multi-step searches or long analysis. Do NOT use for simple single-file tasks — do those directly.",
    "parameters":{"type":"object","properties":{
      "description":{"type":"string","description":"What the subagent should do"},
      "tools":      {"type":"array","items":{"type":"string"},
                     "description":"Tools the subagent may use (default: all except task)"}
    },"required":["description"]}
  }},
  {"type":"function","function":{
    "name":"skill",
    "description":"Load an existing skill file (SKILL.md) by name. Read-only — never attempt to create or write skill files. Use for domain-specific guidance.",
    "parameters":{"type":"object","properties":{
      "name":{"type":"string","description":"Skill name or path, e.g. 'python', 'react', 'testing'"}
    },"required":["name"]}
  }},
  {"type":"function","function":{
    "name":"lsp",
    "description":"Local code intelligence via Python AST — no server needed. Use instead of reading whole files. documentSymbol: list all functions/classes with line numbers. hover: show signature+docstring at line. definition: find where a symbol is defined. references: find all usages. workspace_symbol: search by name across project.",
    "parameters":{"type":"object","properties":{
      "operation":{"type":"string","enum":["documentSymbol","hover","definition","references","workspace_symbol"]},
      "file":     {"type":"string","description":"File path (required for all except workspace_symbol)"},
      "line":     {"type":"integer","description":"1-indexed line number (for hover/definition/references)"},
      "character":{"type":"integer","description":"0-indexed character offset (for hover/definition)"},
      "query":    {"type":"string","description":"Symbol name (for definition/references/workspace_symbol)"}
    },"required":["operation"]}
  }},
  {"type":"function","function":{
    "name":"view_symbol",
"description":"Return a function/class/method by name without reading whole file. Cheaper than read on large files.",
    "parameters":{"type":"object","properties":{
      "path":  {"type":"string","description":"File path"},
      "symbol":{"type":"string","description":"Function/class/method name to find"}
    },"required":["path","symbol"]}
  }},
  {"type":"function","function":{
    "name":"file_index",
    "description":"Call at the start of coding tasks that involve reading or editing existing files. Skip for conversational input, questions about the system, or new-file-only tasks. Returns file paths + symbol names + line numbers (persists across sessions). File listed → use view_symbol directly. File not listed → grep(\"##==\") then grep symbols before any read.",
    "parameters":{"type":"object","properties":{},"required":[]}
  }},
  {"type":"function","function":{
    "name":"verify",
    "description":"Ask the user to visually inspect a file or UI output. Do NOT use for running automated tests — use bash for that. Call when human confirmation is needed before proceeding. See system prompt Tools policy for when this replaces re-reading.",
    "parameters":{"type":"object","properties":{
      "path":   {"type":"string","description":"File or directory path to verify"},
      "reason": {"type":"string","description":"Why you want to verify (optional)"}
    },"required":["path"]}
  }},

]
