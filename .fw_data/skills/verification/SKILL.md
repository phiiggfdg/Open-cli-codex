---
name: verification
description: Chiến lược kiểm thử và xác minh toàn diện sau khi chỉnh sửa code. Dùng để lập kế hoạch test, chọn bộ test hẹp nhất, chạy typecheck/linter và quét regression ở các nhánh phụ.
---

# Verification Strategy — Chiến lược Xác minh & Kiểm thử

*Nguyên tắc bất biến từ Core System Prompt: "After modifying code, verify the change before claiming completion." (Sau khi sửa code, luôn xác minh trước khi tuyên bố hoàn thành).*

Skill này cung cấp quy trình và chiến lược cụ thể để thực hiện việc xác minh một cách nhanh chóng và chính xác.

## 1. Quy tắc "Narrowest Relevant Test" (Bộ kiểm tra hẹp nhất)

Không chạy toàn bộ test suite khổng lồ tốn hàng phút nếu chỉ vừa sửa 1 hàm nhỏ. Hãy chọn mức độ kiểm tra phù hợp:

1. **Syntax / Compilation Check**:
   - Python: `python3 -m py_compile <file>` hoặc AST parse check.
   - JS/TS: `npx tsc --noEmit` hoặc linter syntax.
2. **Focused Unit Test**:
   - Chỉ chạy đúng file test hoặc test case liên quan trực tiếp đến hàm vừa sửa:
     `pytest tests/test_auth.py -k test_login_success`
3. **Typecheck & Linter**:
   - Chạy `mypy <file>` hoặc `ruff check <file>` / `eslint <file>`.

## 2. Quét Call Sites & Phòng ngừa Regression

Một lỗi rất phổ biến là sửa hàm tại định nghĩa nhưng quên cập nhật các nơi gọi khác trong dự án:
- Trước khi coi task là hoàn thành: Dùng `grep` quét toàn bộ codebase tìm tên hàm/biến vừa sửa.
- Đảm bảo tất cả các file gọi (call sites) và các nhánh phụ (parallel branches) đều đã được cập nhật đồng bộ với chữ ký hoặc kiểu dữ liệu mới.

## 3. Xử lý khi môi trường không thể chạy Test

Nếu dự án thiếu môi trường test, thiếu dependency hoặc bị hạn chế quyền:
1. Thực hiện kiểm tra bằng code review tĩnh: Kiểm tra kỹ các nhánh rẽ (`if/else`, `try/except`, `early return`, `default parameters`).
2. Trong câu trả lời cuối cùng cho người dùng: **Nói rõ những gì đã được xác minh và những gì chưa thể chạy thực tế** để người dùng nắm được rủi ro.
