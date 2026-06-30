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

# THỨ TỰ NÀY LÀ BẮT BUỘC — không sắp xếp lại / tách thêm module mà không
# kiểm tra biến cross-file. Tất cả module exec() vào CÙNG 1 namespace, nên
# 1 module có thể dùng global do module load SAU nó định nghĩa, miễn là
# global đó chỉ được ĐỌC lúc hàm thực thi (runtime), không phải lúc load
# module (import-time). Ví dụ thật trong project: 06_tools_fs.py dùng
# _large_read_credits/_file_read_time/_recent_writes/_current_sid, cả 4 đều
# định nghĩa ở 07_tools_more.py (load SAU 06) — vẫn chạy đúng vì các hàm
# trong 06 chỉ được GỌI sau khi toàn bộ 11 module đã load xong. Đổi thứ tự
# ở đây, hoặc tách 1 module thành 2 file mới mà quên đối chiếu biến dùng
# chéo, sẽ gây NameError chỉ lộ ra LÚC AGENT CHẠY (không phải lúc load) —
# rất khó debug nếu không biết kiến trúc này từ trước.
_MODULES = [
    "01_ui.py",
    "01b_aws.py",
    "01c_anthropic.py",
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
    # Modules share one runtime namespace, but they are not standalone entrypoints.
    # Using "__main__" here would execute 10_main.py's guard while loading and then
    # call main() a second time below after the first loop returns.
    _ns = {"__name__": "_fw_runtime", "__file__": str(Path(__file__).resolve())}
    _load_modules(_ns)
    sys.exit(_ns["main"]())


if __name__ == "__main__":
    main()
