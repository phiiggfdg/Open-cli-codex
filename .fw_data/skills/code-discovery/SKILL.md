---
name: code-discovery
description: Chiến lược điều hướng, tra cứu và khám phá codebase lớn. Dùng khi cần tìm hiểu kiến trúc dự án, định vị vị trí code cần sửa, tra cứu symbol hoặc khi bắt đầu task trên codebase chưa quen thuộc.
---

# Code Discovery — Khám phá & Định vị Codebase

Chiến lược tìm kiếm có chủ đích giúp hiểu đúng kiến trúc mà không làm tràn context hay lãng phí token đọc toàn bộ file.

## 1. Thứ tự ưu tiên tra cứu

Thực hiện tra cứu theo thứ tự từ nhẹ/chính xác nhất đến bao quát hơn:

```
file_index
    ↓ (nếu symbol/file đã có trong index)
view_symbol (xem trực tiếp hàm/class)
    ↓ (nếu cần tìm symbol trong file chưa index)
lsp(documentSymbol) hoặc grep("##==") (tìm cấu trúc/sections)
    ↓ (nếu cần tìm keyword / lời gọi hàm)
grep (tìm text/pattern có định hướng kèm glob/path)
    ↓ (nếu không biết file nằm ở đâu)
glob (tìm theo tên file/extension)
    ↓ (chỉ khi đã định vị được vùng cần đọc)
read(offset=N, limit=60) (đọc cửa sổ hẹp quanh vị trí)
```

## 2. Quy tắc đọc file lớn (> 80 dòng)

- **Tuyệt đối không đọc toàn bộ file**: Đọc toàn bộ file hàng trăm dòng làm phình context và dễ bị policy limiter chặn.
- **Quy trình chuẩn**:
  1. `grep` hoặc `view_symbol` để tìm chính xác số dòng của hàm/class/biến cần quan tâm.
  2. Dùng `read(offset=Line-5, limit=50)` để đọc đoạn code hẹp xung quanh ngữ cảnh đó.
- **Anchor Map**: Khi `read` hoặc `edit`, hệ thống tự sinh anchor map ở cuối output để bạn nắm được cấu trúc file mà không cần đọc lại.

## 3. Batching & Tìm kiếm Độc lập

- **Gộp tool calls**: Nếu cần tìm nhiều thông tin độc lập (ví dụ vừa tìm định nghĩa symbol vừa tìm nơi gọi hàm trong file khác), phát ra tất cả tool calls trong **1 lượt phản hồi duy nhất**:
  ```
  [view_symbol(path="auth.py", symbol="login")] + [grep(pattern="login(", path="api/")]
  ```
- **Không re-read**: Những file đã đọc trong turn hiện tại đã có trong RAM context, không đọc lại.
- **Khi kết quả rỗng**: Nếu `view_symbol` hoặc `grep` không có kết quả (`no matches`), chấp nhận kết quả và đổi giả thuyết hoặc mở rộng phạm vi, tuyệt đối không lặp lại cùng một query.

## 4. Điểm dừng sau 3 vòng tra cứu

Nếu đã thực hiện 3 vòng liên tiếp gồm `read`/`grep`/`glob` mà vẫn chưa đủ thông tin để hành động:
1. **DỪNG LẠI** và đánh giá: Liệu giả thuyết ban đầu có sai không?
2. Cân nhắc dùng `question` để hỏi người dùng nếu yêu cầu bị thiếu hoặc mơ hồ.
3. Không cố sửa code mò khi chưa đủ bằng chứng.
