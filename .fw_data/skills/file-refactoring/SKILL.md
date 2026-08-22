---
name: file-refactoring
description: Quy trình tái cấu trúc code, tách module, di chuyển khối code và chia nhỏ file lớn. Dùng khi tái cấu trúc project, tách file > 80 dòng, trích xuất hàm/class sang file mới hoặc tái tổ chức thư mục.
---

# File Refactoring — Tái cấu trúc & Di chuyển Code

Refactor an toàn, nguyên tử (atomic), không gây mất mát code và không làm vỡ liên kết trong dự án.

## 1. Nguyên tắc cốt lõi: Dùng `extract` thay vì gõ lại

- **Tuyệt đối không đọc rồi gõ lại (`write`/`edit`)**: Khi chuyển hàm, class hoặc khối code từ file A sang file B, việc đọc rồi gõ lại qua prompt vừa lãng phí token vừa dễ gây lỗi gõ sai/thiếu dòng hoặc bị truncation.
- **Dùng tool `extract`**:
  - `extract(src="old.py", start=50, end=120, dst="new.py", mode="move")`: Tự động cắt đúng dòng 50–120 từ `old.py` đưa sang `new.py` (tạo mới nếu chưa có).
  - `mode="move"`: Xóa khối code khỏi file nguồn sau khi chuyển thành công.
  - `mode="copy"`: Giữ nguyên file nguồn, chỉ sao chép sang file đích.
  - `extract` có cơ chế kiểm tra `mtime` chống race condition và tự lưu snapshot vào `undo_stack`.

## 2. Quy trình 4 bước khi tách Module

1. **Định vị & Xác định dòng**:
   - Dùng `view_symbol` hoặc `grep` để biết chính xác `start_line` và `end_line` của khối code cần chuyển.
2. **Thực hiện trích xuất**:
   - Gọi `extract` để chuyển khối code sang file đích.
3. **Cập nhật Import & Call sites**:
   - Thêm câu lệnh `import` vào file đích cho các dependency mà khối code cần.
   - Thêm câu lệnh `import` vào file nguồn (hoặc các file gọi cũ) để trỏ tới module mới.
   - Dùng `grep` để quét toàn bộ codebase tìm mọi nơi gọi cũ và cập nhật đường dẫn import nếu cần.
4. **Xác minh (Verification)**:
   - Chạy linter, typecheck hoặc unit test để đảm bảo không bị `NameError` hoặc `ImportError`.

## 3. Tránh lỗi đường dẫn lặp (Double-Nesting Paths)

- Kết quả từ `glob` hoặc `file_index` có thể chứa tiền tố thư mục session/sandbox (ví dụ `proj_dir/utils.py`).
- Các tool `write`/`edit`/`extract` tự động resolve theo sandbox. Hãy loại bỏ tiền tố trùng lặp trước khi truyền vào tool để tránh tạo ra đường dẫn lặp dạng `proj_dir/proj_dir/utils.py`.
