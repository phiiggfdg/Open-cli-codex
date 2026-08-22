---
name: debugging
description: Quy trình 4 bước debug bài bản (Reproduce → Isolate → Fix → Verify). Dùng khi điều tra lỗi, phân tích stacktrace/exception, giải quyết bug hóc búa hoặc khi test bị fail.
---

# Debugging — Quy trình Điều tra & Sửa lỗi 4 Bước

Phương pháp tiếp cận khoa học, tránh sửa mò, sửa đoán hoặc thử-sai vô định hướng.

```
[1. Reproduce] ──► [2. Isolate] ──► [3. Fix] ──► [4. Verify]
```

## Bước 1: Reproduce (Tái hiện lỗi)
- Không vội sửa code ngay khi chỉ mới đọc mô tả lỗi sơ sài.
- Xác định rõ: Input đầu vào là gì? Kết quả mong đợi là gì? Kết quả thực tế nhận được là gì?
- Chạy lệnh test hoặc lệnh tối giản nhất để quan sát lỗi trực tiếp:
  - Xem kỹ `exit_code`, `error_class`, `retry_hint`, `stdout` và `stderr`.

## Bước 2: Isolate (Cô lập nguyên nhân gốc)
- **Đọc Stacktrace từ dưới lên trên**: Tìm đúng dòng code của dự án phát sinh exception (bỏ qua các tầng wrapper bên ngoài).
- Dùng `view_symbol` hoặc `read(offset)` quanh dòng gây lỗi để phân tích ngữ cảnh.
- Kiểm tra toàn diện các nhánh điều kiện:
  - Giá trị biến có thể là `None`, chuỗi rỗng `""`, danh sách rỗng `[]` không?
  - Nhánh `except` có đang nuốt lỗi im lặng hoặc gán giá trị sai không?
  - Có sự bất đồng bộ (async/race condition) hay sai lệch kiểu dữ liệu (type mismatch) không?
- **Phân biệt Giả định và Sự thật**: Nếu chưa xem code của một hàm phụ trợ, hãy nói "Giả định hàm trả về X" và dùng tool kiểm tra trước khi kết luận.

## Bước 3: Fix (Sửa đúng nguyên nhân gốc)
- Sửa tại nguồn gốc phát sinh lỗi, không vá bề mặt (chẳng hạn không thêm `if obj is not None:` tràn lan nếu lỗi thật là do hàm trước đó trả về dữ liệu sai cấu trúc).
- Dùng `edit` chính xác với `old_str` độc nhất.

## Bước 4: Verify (Xác minh kết quả)
- Chạy lại bài test hoặc câu lệnh ở Bước 1 để chứng minh lỗi đã được giải quyết.
- Kiểm tra xem bản sửa lỗi có gây ảnh hưởng phụ (side-effects) lên các chức năng xung quanh không.

## Quy tắc Anti-Loop khi Debug
- Nếu sửa và thử lại 3 lần liên tiếp vẫn thất bại:
  - **DỪNG LẠI NGAY LẬP TỨC**.
  - Không thử tiếp cùng một hướng đi hay thay đổi cú pháp vu vơ.
  - Đánh giá lại toàn bộ giả thuyết từ đầu, hoặc dùng `question` để tham vấn người dùng về hành vi mong muốn.
