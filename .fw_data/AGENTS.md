# fw.py — Global Agent Rules

## Simplicity First (ưu tiên cao nhất)

**Minimum code giải quyết đúng vấn đề. Không thêm gì ngoài yêu cầu.**

- Không thêm feature ngoài những gì được hỏi.
- Không tạo abstraction cho code chỉ dùng 1 lần.
- Không thêm "flexibility" hay "configurability" không ai xin.
- Không xử lý error cho tình huống không thể xảy ra.
- Nếu viết 200 dòng mà có thể là 50 dòng → viết lại.

Tự hỏi: "Senior engineer có nói cái này overcomplicated không?" Nếu có → đơn giản hóa.

## Codebase này

- **Ngôn ngữ:** Python 3, target Termux/Android ARM64.
- **Entry point:** `fw.py` (loader) → load theo thứ tự `01_ui.py` → `10_main.py` vào cùng 1 namespace.
- **Không có import giữa các module** — tất cả chạy trong shared namespace, biến global là shared.
- **`.fw_data/src/`** là thư mục ẩn — không xuất hiện trong file listing thông thường.


## Quy tắc chỉnh sửa

- Sửa đúng file theo module map — không đặt logic vào sai layer.
- Biến global dùng chung → khai báo ở module phù hợp nhất, không tạo bản sao.
- Thêm feature mới → hỏi trước nếu ảnh hưởng >2 module.
- Không thay đổi cấu trúc load order (`_MODULES` trong `fw.py`) trừ khi thực sự cần.

## Shared namespace — hệ quả quan trọng

Tất cả module chạy trong **cùng 1 namespace** qua `exec()`. Hệ quả:
- **Không dùng `import` giữa các file** trong `.fw_data/src/` — symbol đã có sẵn trong namespace.
- **Không dùng `if __name__ == "__main__"`** trong bất kỳ module nào — chỉ `fw.py` mới có.
- **Không redeclare global** đã khai báo ở module trước — ghi đè sẽ phá vỡ logic.

## Thêm module mới

Nếu cần thêm file module mới vào `.fw_data/src/`:
1. Đặt tên theo pattern `NN_name.py` (số thứ tự tiếp theo).
2. Thêm vào `_MODULES` trong `fw.py` đúng vị trí phụ thuộc.
3. Cập nhật module map ở AGENTS.md này.

## Môi trường: Termux / Android

- `pip install` luôn cần `--break-system-packages`.
- Không có `sudo` — không dùng `apt`, `systemctl`, hay lệnh cần root.
- Home path: `/data/data/com.termux/files/home`.

## Section markers

File mới >80 dòng dùng pattern: `# ##== NAME ==##`. Ví dụ:
```python
# ##== PROVIDER ==##
...code...
# ##== /end PROVIDER ==##
```

## Output / UX

- Không emoji trong output của agent.
- Tóm tắt sau task: files đã thay đổi + cách chạy/verify. Ngắn gọn.
- Không giải thích lại những gì đã rõ.
p theo).
2. Thêm vào `_MODULES` trong `fw.py` đúng vị trí phụ thuộc.
3. Cập nhật module map ở AGENTS.md này.

## Môi trường: Termux / Android

- `pip install` luôn cần `--break-system-packages`.
- Không có `sudo` — không dùng `apt`, `systemctl`, hay lệnh cần root.
- Home path: `/data/data/com.termux/files/home`.

## Section markers

File mới >80 dòng dùng pattern: `# ##== NAME ==##`. Ví dụ:
```python
# ##== PROVIDER ==##
...code...
# ##== /end PROVIDER ==##
```

## Output / UX

- Không emoji trong output của agent.
- Tóm tắt sau task: files đã thay đổi + cách chạy/verify. Ngắn gọn.
- Không giải thích lại những gì đã rõ.
