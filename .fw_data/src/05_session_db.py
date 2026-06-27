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
    conn.execute("INSERT INTO file_snapshot VALUES (?,?,?,?,?,?)",
                 (str(uuid.uuid4()), sid, path, before, after, int(time.time())))
    conn.commit()

def snapshots_load(conn, sid):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM file_snapshot WHERE session_id=? ORDER BY created_at",
        (sid,)).fetchall()]

# ════════════════════════════════════════════════════════════════════════════
# TOKEN / COMPACT
# ════════════════════════════════════════════════════════════════════════════

def estimate_tokens(messages):
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
Write in Vietnamese, except for exact commands, file paths, errors, identifiers, and quoted output."""

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
    print(f"\n{color}{'─'*56}{R}")
    print(f"  {BOLD}[compact]{R} Context đang ở {pct}% ({current:,} tok).")
    print(f"  {DIM}Cần tóm tắt lịch sử cũ để giải phóng không gian.{R}")
    print(f"  {CYAN}Tóm tắt và xoá các tin nhắn cũ? [Y/n]: {R}", end="")
    try:
        ans = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "y"
    if ans in ("n", "no", "không", "k"):
        print(f"  {YELLOW}Bỏ qua compact — context có thể bị tràn.{R}")
        return messages
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
    "description":"Execute shell command. Use for build/test/git/install. NOT for file read/write. Output includes diagnostic fields: exit_code, stderr, error_class, retry_hint.",
    "parameters":{"type":"object","properties":{
      "command":{"type":"string"},
      "timeout":{"type":"integer","description":"Seconds (default 30)"}
    },"required":["command"]}
  }},
  {"type":"function","function":{
    "name":"read",
    "description":"Read file with line numbers or list directory as tree. Output includes an auto-generated Anchor map (functions/classes/CSS rules/headings near your offset) — check it first before grepping again. For files >80 lines: read with a small offset+limit first; use the anchor map or grep to jump to the right section instead of reading the whole file. Never call without offset on large files.",
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
    "description":"Simple replacement for small one-line or single-location changes only. For multiple locations or large sections, use multiedit or apply_patch instead.",
    "parameters":{"type":"object","properties":{
      "path":   {"type":"string"},
      "old_str":{"type":"string","description":"Exact text to find (must be unique in file). Do NOT include line-number prefixes shown by the read tool."},
      "new_str":{"type":"string","description":"Replacement text"}
    },"required":["path","old_str","new_str"]}
  }},
  {"type":"function","function":{
    "name":"multiedit",
    "description":"Multiple targeted replacements in one file, one call. Use when changing 2-5 known locations. Each old_str must be unique.",
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
    "description":"Search regex in files. Returns file:line:content.",
    "parameters":{"type":"object","properties":{
      "pattern":{"type":"string","description":"Regex pattern"},
      "path":   {"type":"string","description":"File or directory (default: cwd)"},
      "glob":   {"type":"string","description":"Only files matching this glob e.g. '*.py'"}
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
    "description":"Update todo list only for multi-step tasks. Do not use for small/simple tasks. Batch updates at major milestones (~50% progress), completion, or blocker/scope changes; avoid per-step updates.",
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
    "name":"set_tools",
    "description":"Declare which tools you plan to focus on next. This is a planning hint only; the full tool schema remains available to preserve prompt-cache stability. Always include set_tools itself.",
    "parameters":{"type":"object","properties":{
      "tools":{"type":"array","items":{"type":"string"},
               "description":"Tool names to keep active e.g. ['bash','write','set_tools']"}
    },"required":["tools"]}
  }},
  {"type":"function","function":{
    "name":"file_index",
    "description":"Call at the start of coding tasks that involve reading or editing existing files. Skip for conversational input, questions about the system, or new-file-only tasks. Returns file paths + symbol names + line numbers (persists across sessions). File listed → use view_symbol directly. File not listed → grep(\"##==\") then grep symbols before any read.",
    "parameters":{"type":"object","properties":{},"required":[]}
  }},
  {"type":"function","function":{
    "name":"verify",
    "description":"Ask the user to visually inspect a file or UI output. Use INSTEAD of calling read/glob/bash(ls) after a write. Do NOT use for running automated tests — use bash for that. Call when human confirmation is needed before proceeding.",
    "parameters":{"type":"object","properties":{
      "path":   {"type":"string","description":"File or directory path to verify"},
      "reason": {"type":"string","description":"Why you want to verify (optional)"}
    },"required":["path"]}
  }},

]

# Tất cả tool names (để set_tools validate)
ALL_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

# Tool focus hint only. Full TOOLS schema stays stable for prompt-cache reuse.
_active_tools: set | None = None

