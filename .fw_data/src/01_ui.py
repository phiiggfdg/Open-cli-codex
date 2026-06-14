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
    "/model", "/agent", "/session", "/sessions", "/todos", "/compact",
    "/clear", "/delete", "/deleteall", "/cd", "/title", "/tokens",
    "/undo", "/redo", "/diff", "/sandbox", "/export", "/cache", "/checkpoint",
    "/perm", "/perms", "/skills", "/setkey", "/init", "/rules",
    "/commands", "/sequential", "/batch", "/commit", "/review", "/help", "/mcp",
]

SLASH_DESC = {
    "/model":      "đổi model",
    "/agent":      "đổi agent mode (build/plan)",
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
    Raw-mode input với:
      - Slash hint: gõ '/' hiển thị gợi ý lệnh (đã fix cursor)
      - ↑↓ history: duyệt lịch sử input như shell
      - @file Tab complete: gõ '@foo' rồi Tab → gợi ý file khớp
    Fallback về _multiline_input nếu terminal không hỗ trợ raw mode.
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
    hist_idx = len(_input_history)   # trỏ vào "dòng mới" (past end)
    hist_saved = ""                  # lưu buf hiện tại khi bắt đầu duyệt history

    # ── helpers ──────────────────────────────────────────────────────────────
    # Số dòng hint đang hiện bên dưới dòng input — dùng để clear chính xác
    n_hint_lines = 0

    _prev_wrapped = [1]

    def _redraw(text: str, force: bool = False):
        """Xoá và vẽ lại prompt + text.
        force=True khi backspace/history (cần redraw full dù đang wrap).
        Khi chỉ thêm ký tự mới và đang wrap: chỉ in ký tự, không cursor-up.
        """
        import re as _re
        _ansi = _re.compile(r"\033\[[0-9;]*m")
        visible_prompt = len(_ansi.sub("", prompt))
        cols = shutil.get_terminal_size((80, 20)).columns
        total_len = visible_prompt + len(text)
        cur_wrapped = max(1, (total_len + cols - 1) // cols)

        if not force and cur_wrapped > 1 and cur_wrapped >= _prev_wrapped[0]:
            # Đang wrap, chỉ thêm ký tự → in thêm ký tự cuối, terminal tự wrap
            sys.stdout.write(text[-1] if text else "")
        else:
            # Redraw full: lên về dòng đầu dựa vào wrap lần trước
            up = _prev_wrapped[0] - 1
            if up > 0:
                sys.stdout.write(f"\033[{up}A")
            sys.stdout.write(f"\r\033[J{prompt}{text}")

        _prev_wrapped[0] = cur_wrapped
        sys.stdout.flush()


    def _clear_hints():
        """Xoá đúng số dòng hint đang hiện, đưa cursor về dòng input."""
        nonlocal n_hint_lines
        if n_hint_lines == 0:
            return
        # Xuống tới dòng cuối hint, xoá từng dòng, rồi lên lại
        for _ in range(n_hint_lines):
            sys.stdout.write("\r\n\033[K")
        # Lên lại đúng n dòng
        sys.stdout.write(f"\033[{n_hint_lines}A")
        sys.stdout.flush()
        n_hint_lines = 0

    def _show_slash_hints(text: str):
        nonlocal n_hint_lines
        if not text.startswith("/"):
            return
        hints = _slash_hint(text)
        if not hints:
            return
        if len(hints) <= 4:
            for cmd in hints:
                desc = SLASH_DESC.get(cmd, "")
                sys.stdout.write(f"\r\n{CYAN}{cmd}{R}  {GRAY}{desc}{R}\033[K")
            n = len(hints)
        else:
            hint_str = "  ".join(hints[:10])
            sys.stdout.write(f"\r\n{DIM}  {hint_str}{R}\033[K")
            n = 1
        # Lên lại + redraw dòng input
        sys.stdout.write(f"\033[{n}A\r")
        sys.stdout.write(prompt + text)
        sys.stdout.flush()
        n_hint_lines = n

    def _show_at_hints(text: str):
        """Hiện gợi ý @file bên dưới cursor."""
        nonlocal n_hint_lines
        m = re.search(r"@([\w./\\-]*)$", text)
        if not m:
            return
        prefix = m.group(1)
        files = _at_file_complete(prefix)
        if not files:
            return
        # Show tối đa 4 file
        show = files[:4]
        for f in show:
            sys.stdout.write(f"\r\n{GREEN}@{f}{R}\033[K")
        if len(files) > 4:
            sys.stdout.write(f"\r\n{DIM}  ...+{len(files)-4} more{R}\033[K")
            show_n = len(show) + 1
        else:
            show_n = len(show)
        sys.stdout.write(f"\033[{show_n}A\r")
        sys.stdout.write(prompt + text)
        sys.stdout.flush()
        n_hint_lines = show_n

    def _do_tab_complete(buf: list[str]) -> list[str]:
        """Tab pressed: complete @file token tại cuối buf."""
        text = "".join(buf)
        m = re.search(r"@([\w./\\-]*)$", text)
        if not m:
            return buf
        prefix = m.group(1)
        files = _at_file_complete(prefix)
        if not files:
            return buf
        if len(files) == 1:
            # Duy nhất → complete luôn
            completed = text[:m.start()] + "@" + files[0]
            return list(completed)
        # Tìm common prefix
        common = files[0]
        for f in files[1:]:
            while not f.startswith(common):
                common = common[:-1]
                if not common:
                    break
        if common and len(common) > len(prefix):
            completed = text[:m.start()] + "@" + common
            return list(completed)
        return buf

    # ── main raw loop ─────────────────────────────────────────────────────────
    try:
        _tty.setraw(fd)
        # Bật bracketed paste mode: paste wrap trong \x1b[200~...text...\x1b[201~
        sys.stdout.write("\x1b[?2004h")
        sys.stdout.write(prompt)
        sys.stdout.flush()

        while True:
            ch = sys.stdin.read(1)

            # ── Enter ─────────────────────────────────────────────────────────
            if ch in ("\r", "\n"):
                _clear_hints()
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

            # ── Ctrl-C ────────────────────────────────────────────────────────
            if ch == "\x03":
                _clear_hints()
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return None

            # ── Ctrl-D ────────────────────────────────────────────────────────
            if ch == "\x04":
                _clear_hints()
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return None

            # ── Tab: @file complete ───────────────────────────────────────────
            if ch == "\t":
                _clear_hints()
                text_before = "".join(buf)
                buf = _do_tab_complete(buf)
                text_after = "".join(buf)
                if text_after != text_before:
                    _redraw(text_after)
                else:
                    # Không complete được → show gợi ý
                    _show_at_hints(text_after)
                continue

            # ── Escape sequence (arrow keys, etc.) ────────────────────────────
            if ch == "\x1b":
                seq = sys.stdin.read(1)
                if seq == "[":
                    arrow = sys.stdin.read(1)

                    # Bracketed paste begin: \x1b[200~
                    if arrow == "2":
                        rest = sys.stdin.read(2)  # "0~"
                        if rest == "0~":
                            pasted = []
                            while True:
                                pc = sys.stdin.read(1)
                                if pc == "\x1b":
                                    sys.stdin.read(4)  # "[201~"
                                    break
                                pasted.append(pc)
                            paste_text = "".join(pasted).replace("\r","").replace("\n"," ").strip()
                            buf.extend(list(paste_text))
                            hist_idx = len(_input_history)
                            text = "".join(buf)
                            _clear_hints()
                            _redraw(text)
                        continue

                    # ↑ history
                    if arrow == "A":
                        if not _input_history:
                            continue
                        if hist_idx == len(_input_history):
                            hist_saved = "".join(buf)  # lưu dòng đang gõ
                        if hist_idx > 0:
                            hist_idx -= 1
                            buf = list(_input_history[hist_idx])
                            _clear_hints()
                            _redraw("".join(buf), force=True)
                        continue

                    # ↓ history
                    if arrow == "B":
                        if hist_idx < len(_input_history):
                            hist_idx += 1
                            if hist_idx == len(_input_history):
                                buf = list(hist_saved)
                            else:
                                buf = list(_input_history[hist_idx])
                            _clear_hints()
                            _redraw("".join(buf), force=True)
                        continue

                    # ← → Home End — bỏ qua (cursor move không hỗ trợ)
                continue

            # ── Backspace ─────────────────────────────────────────────────────
            if ch in ("\x7f", "\x08"):
                if buf:
                    buf.pop()
                    text = "".join(buf)
                    _clear_hints()
                    _redraw(text, force=True)
                    if text.startswith("/"):
                        _show_slash_hints(text)
                    elif "@" in text:
                        _show_at_hints(text)
                continue

            # ── Ký tự bình thường ─────────────────────────────────────────────
            buf.append(ch)
            hist_idx = len(_input_history)  # reset history index khi gõ mới

            text = "".join(buf)
            _clear_hints()
            _redraw(text)
            if text.startswith("/"):
                _show_slash_hints(text)
            elif "@" in text:
                _show_at_hints(text)

    except Exception:
        return _multiline_input(prompt)
    finally:
        try:
            sys.stdout.write("\x1b[?2004l")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass

