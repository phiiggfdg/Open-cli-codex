#!/usr/bin/env python3
"""
fw.py — Fireworks AI Coding Agent CLI
Inspired by anomalyco/opencode (MIT license)

Tools: bash, read, write, edit, multiedit,
       glob, grep, webfetch, websearch, todowrite, todoread, question,
       apply_patch, task, skill, lsp, file_index, view_symbol,
       set_tools, verify
Session: SQLite, resume, compaction, token tracking, undo/redo
Agents:  build (full), plan (read-only)
Perms:   per-tool allow/ask/deny
"""

import os, sys, json, re, sqlite3, uuid, time, subprocess, shlex
import difflib, urllib.request, urllib.parse, urllib.error, threading, shutil
from pathlib import Path
from datetime import datetime

# ── Màu — Open CLI Codex · amber-on-dark hacker palette ─────────────────────
R="\033[0m"; BOLD="\033[1m"
# Primary: warm amber / gold
CYAN="\033[38;5;214m"       # amber-gold  (thay cyan mặc định)
TEAL="\033[38;5;220m"       # bright gold (accent mạnh)
# Secondary: xanh lá terminal kinh điển
GREEN="\033[38;5;114m"      # muted terminal green
BLUE="\033[38;5;74m"        # steel blue (plan mode)
# Alert / warning
YELLOW="\033[38;5;229m"     # pale yellow
RED="\033[38;5;196m"        # sharp red
# Neutral
WHITE="\033[38;5;231m"      # near-white
GRAY="\033[38;5;240m"       # dark gray
MAGENTA="\033[38;5;177m"    # soft violet (giữ cho backward compat)
DIM="\033[2m"

# ── Spinner ──────────────────────────────────────────────────────────────────
class Spinner:
    """Hiển thị spinner animation trên terminal khi AI đang xử lý."""
    # Rotating bar — clean, universal
    FRAMES = ["─", "\\", "│", "/", "─", "\\", "│", "/"]
    # Matrix rain drops — chars hiện nhanh bên cạnh label
    _RAIN  = "01アイウエオカキクケコサシスセソタチツテトナニヌネノ"

    def __init__(self, label="Thinking"):
        self.label   = label
        self._stop   = threading.Event()
        self._thread = None
        self._start_t = 0.0

    def _run(self):
        import random as _r
        i = 0
        self._start_t = time.time()
        rain_buf = ["  ", "  ", "  "]
        while not self._stop.is_set():
            frame   = self.FRAMES[i % len(self.FRAMES)]
            elapsed = time.time() - self._start_t
            elapsed_s = f" {elapsed:.1f}s" if elapsed >= 1 else ""
            if i % 2 == 0:
                rain_buf = [_r.choice(self._RAIN) for _ in range(3)]
            rain_str = "".join(f"{GRAY}{c}{R}" for c in rain_buf)
            sys.stdout.write(
                f"\r{TEAL}{frame}{R} {CYAN}{self.label}{R} "
                f"{rain_str}"
                f"{GRAY}{elapsed_s}{R}"
                f"   "
            )
            sys.stdout.flush()
            time.sleep(0.09)
            i += 1
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()

# ── Slash-complete ────────────────────────────────────────────────────────────
SLASH_COMMANDS = [
    "/model", "/agent", "/mode", "/session", "/sessions", "/todos", "/compact",
    "/clear", "/delete", "/deleteall", "/cd", "/title", "/tokens",
    "/undo", "/redo", "/diff", "/sandbox", "/export", "/cache", "/checkpoint",
    "/perm", "/perms", "/skills", "/setkey", "/deletekey", "/init", "/rules",
    "/commands", "/sequential", "/batch", "/commit", "/review", "/help", "/mcp",
]

SLASH_DESC = {
    "/model":      "đổi model",
    "/agent":      "đổi agent mode (build/plan)",
    "/mode":       "bật/tắt thinking mode (nếu model hỗ trợ)",
    "/session":    "info session hiện tại",
    "/sessions":   "switch/tạo session",
    "/todos":      "xem todo list",
    "/compact":    "compact context thủ công",
    "/clear":      "xoá lịch sử chat",
    "/delete":     "xoá session",
    "/deleteall":  "xoá TẤT CẢ session",
    "/cd":         "đổi thư mục",
    "/title":      "đổi tên session",
    "/tokens":     "xem token usage",
    "/cache":      "xem/debug file cache",
    "/checkpoint": "lưu/xem mốc tiến độ",
    "/undo":       "undo thay đổi file",
    "/redo":       "redo đã undo",
    "/diff":       "xem file đã thay đổi",
    "/sandbox":    "xem project_dir sandbox",
    "/export":     "xuất conversation ra markdown",
    "/perm":       "đặt permission tool",
    "/perms":      "xem permission hiện tại",
    "/skills":     "liệt kê skills",
    "/setkey":     "đổi API key",
    "/deletekey":  "xoá API key đã lưu",
    "/init":       "tạo AGENTS.md cho project",
    "/rules":      "xem AGENTS.md đang active",
    "/commands":   "liệt kê custom commands",
    "/sequential": "chuyển sang mode từng bước (tốn token hơn, an toàn hơn)",
    "/batch":      "chuyển về mode gộp tool calls (mặc định, tiết kiệm token)",
    "/commit":     "AI đọc git diff --staged và tự viết commit message",
    "/review":     "AI review code đã thay đổi trong session hiện tại",
    "/help":       "xem tất cả lệnh",
    "/mcp":        "quản lý MCP server (Command Code) — list/add/remove/status",
}

def _slash_hint(prefix: str) -> list[str]:
    """Trả về danh sách lệnh khớp với prefix."""
    return [c for c in SLASH_COMMANDS if c.startswith(prefix)]

_input_history: list[str] = []  # load từ file khi main() khởi động

def _multiline_input_with_hint(prompt: str) -> str | None:
    """
    Raw-mode input với slash hint, history, @file complete.
    Hint hiện trên 1 dòng phía dưới prompt, xóa sạch mỗi keystroke.
    """
    import sys, termios, tty as _tty

    if not sys.stdin.isatty():
        return _multiline_input(prompt)

    try:
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
    except Exception:
        return _multiline_input(prompt)

    buf: list[str] = []
    hist_idx  = len(_input_history)
    hist_saved = ""
    has_hint  = [False]

    # ── render: hint hiện inline sau text trên cùng dòng ─────────────────────
    _ANSI_RE = re.compile(r"\033\[[0-9;]*m")

    def _visible_len(s: str) -> int:
        """Độ dài hiển thị thực (bỏ ANSI escape codes)."""
        return len(_ANSI_RE.sub("", s))

    # theo dõi số dòng đang hiển thị để xoá đúng khi keystroke tiếp theo
    _cur_lines = [1]  # bắt đầu là 1 dòng

    def _redraw(text: str, hint: str = ""):
        """Xoá đúng số dòng cũ rồi vẽ lại từ đầu."""
        term_w = shutil.get_terminal_size((80, 24)).columns
        # lên về dòng đầu tiên của input
        if _cur_lines[0] > 1:
            sys.stdout.write(f"\033[{_cur_lines[0]-1}A")
        sys.stdout.write("\r\033[J")  # xoá từ đây xuống hết

        line = prompt + text
        if hint:
            line += f"  {DIM}{hint}{R}"
        sys.stdout.write(line)

        # tính số dòng mới chiếm sau khi vẽ
        visible = _visible_len(prompt + text) + (_visible_len(hint) + 2 if hint else 0)
        _cur_lines[0] = max(1, (visible + term_w - 1) // term_w)

        if hint:
            hint_visible = _visible_len(f"  {hint}")
            sys.stdout.write(f"\033[{hint_visible}D")
        sys.stdout.flush()

    def _render(text: str):
        hint = ""
        if text.startswith("/"):
            hints = _slash_hint(text)
            if hints:
                hint = "  ".join(hints[:6])
        elif "@" in text:
            m = re.search(r"@([\w./\\-]*)$", text)
            if m:
                files = _at_file_complete(m.group(1))
                if files:
                    hint = f"@{files[0]}" + (f"  +{len(files)-1}" if len(files) > 1 else "")
        has_hint[0] = bool(hint)
        _redraw(text, hint)

    def _clear_hint(current_buf: list):
        """Xóa hint, giữ text."""
        has_hint[0] = False
        _redraw("".join(current_buf))

    # ── main raw loop ─────────────────────────────────────────────────────────
    try:
        _tty.setraw(fd)
        sys.stdout.write("\x1b[?2004h")
        sys.stdout.write(prompt)
        sys.stdout.flush()

        while True:
            ch = sys.stdin.read(1)

            # Enter
            if ch in ("\r", "\n"):
                # chỉ xoá hint, không redraw toàn bộ (tránh cursor nhảy lên)
                if has_hint[0]:
                    _render("".join(buf))   # vẽ lại không hint
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                line = "".join(buf).strip()
                if line.endswith("\\"):
                    buf = list(line[:-1]) + ["\n"]
                    sys.stdout.write(f"{DIM}... {R}")
                    sys.stdout.flush()
                    continue
                if line:
                    _input_history.append(line)
                    history_save(_input_history)
                return line or None

            # Ctrl-C / Ctrl-D
            if ch in ("\x03", "\x04"):
                if has_hint[0]:
                    _render("".join(buf))
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return None

            # Tab: @file complete
            if ch == "\t":
                text = "".join(buf)
                m = re.search(r"@([\w./\\-]*)$", text)
                if m:
                    files = _at_file_complete(m.group(1))
                    if len(files) == 1:
                        buf = list(text[:m.start()] + "@" + files[0])
                    elif files:
                        common = files[0]
                        for f in files[1:]:
                            while not f.startswith(common):
                                common = common[:-1]
                        if len(common) > len(m.group(1)):
                            buf = list(text[:m.start()] + "@" + common)
                _render("".join(buf))
                continue

            # Escape sequence (arrow keys)
            if ch == "\x1b":
                seq = sys.stdin.read(1)
                if seq == "[":
                    arrow = sys.stdin.read(1)
                    # Bracketed paste
                    if arrow == "2":
                        rest = sys.stdin.read(2)
                        if rest == "0~":
                            pasted = []
                            while True:
                                pc = sys.stdin.read(1)
                                if pc == "\x1b":
                                    sys.stdin.read(4)
                                    break
                                pasted.append(pc)
                            paste_text = "".join(pasted).replace("\r","").replace("\n"," ").strip()
                            buf.extend(list(paste_text))
                            hist_idx = len(_input_history)
                            _render("".join(buf))
                        continue
                    # ↑ history
                    if arrow == "A":
                        if _input_history:
                            if hist_idx == len(_input_history):
                                hist_saved = "".join(buf)
                            if hist_idx > 0:
                                hist_idx -= 1
                                buf = list(_input_history[hist_idx])
                                _render("".join(buf))
                        continue
                    # ↓ history
                    if arrow == "B":
                        if hist_idx < len(_input_history):
                            hist_idx += 1
                            buf = list(hist_saved if hist_idx == len(_input_history) else _input_history[hist_idx])
                            _render("".join(buf))
                        continue
                continue

            # Backspace
            if ch in ("\x7f", "\x08"):
                if buf:
                    buf.pop()
                    _render("".join(buf))
                continue

            # Ký tự bình thường
            buf.append(ch)
            hist_idx = len(_input_history)
            _render("".join(buf))

    except Exception:
        return _multiline_input(prompt)
    finally:
        try:
            sys.stdout.write("\x1b[?2004l")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass
