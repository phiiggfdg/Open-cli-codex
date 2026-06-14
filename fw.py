#!/usr/bin/env python3
"""
fw.py — Open CLI Codex
Author: Trần Tuấn Phi
GitHub: https://github.com/phiiggfdg/Open-cli-codex

Source được tách thành nhiều module nhỏ trong .fw_data/src/ (thư mục ẩn,
không lộ ra khi liệt kê project bằng các tool thông thường). File này chỉ
là loader: nạp các module theo đúng thứ tự gốc vào CÙNG một namespace,
giữ nguyên hành vi như file fw.py monolith trước đây (không cần sửa
import/global giữa các phần).
"""

import sys
from pathlib import Path

def _find_src_dir() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [
        here / ".fw_data" / "src",
        Path(sys.prefix) / ".fw_data" / "src",
        here.parent.parent / ".fw_data" / "src",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "Khong tim thay .fw_data/src/ - kiem tra lai cau truc cai dat."
    )


_SRC_DIR = _find_src_dir()

_MODULES = [
    "01_ui.py",
    "02_provider.py",
    "03_mcp.py",
    "04_agent_cache.py",
    "05_session_db.py",
    "06_tools_fs.py",
    "07_tools_more.py",
    "08_undo_dispatch.py",
    "09_api_system.py",
    "10_main.py",
]


def _load_modules(namespace: dict) -> None:
    for fname in _MODULES:
        path = _SRC_DIR / fname
        src = path.read_text(encoding="utf-8")
        code = compile(src, str(path), "exec")
        exec(code, namespace)


def main():
    """Entry point for 'opencli' command after pip install."""
    _ns = {"__name__": "__main__", "__file__": str(Path(__file__).resolve())}
    _load_modules(_ns)
    sys.exit(_ns["main"]())


if __name__ == "__main__":
    main()
