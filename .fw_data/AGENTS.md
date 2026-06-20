## Simplicity First (ưu tiên cao nhất)

**Minimum code giải quyết đúng vấn đề. Không thêm gì ngoài yêu cầu.**

- Không thêm feature ngoài những gì được hỏi.
- Không tạo abstraction cho code chỉ dùng 1 lần.
- Không thêm "flexibility" hay "configurability" không ai xin.
- Không xử lý error cho tình huống không thể xảy ra.
- Nếu viết 200 dòng mà có thể là 50 dòng → viết lại.

Tự hỏi: "Senior engineer có nói cái này overcomplicated không?" Nếu có → đơn giản hóa.


## Quy tắc chỉnh sửa

- Sửa đúng file theo module map — không đặt logic vào sai layer.
- Biến global dùng chung → khai báo ở module phù hợp nhất, không tạo bản sao.
- Thêm feature mới → hỏi trước nếu ảnh hưởng >2 module.

## Môi trường: Termux / Android

- `pip install` luôn cần `--break-system-packages`.
- Không có `sudo` — không dùng `apt`, `systemctl`, hay lệnh cần root.

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