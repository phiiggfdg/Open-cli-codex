---
name: large-change
description: Quy trình lập kế hoạch và thực thi thay đổi lớn, nhiều module hoặc tính năng phức tạp. Dùng khi thêm feature lớn, tái cấu trúc nhiều tầng kiến trúc, hoặc khi task tác động lên nhiều file trong dự án.
---

# Large Change — Quy trình Thực thi Thay đổi Lớn

Áp dụng cho các nhiệm vụ phức tạp, ảnh hưởng nhiều module, đòi hỏi tính kỷ luật cao để tránh làm gãy dự án giữa chừng.

## 1. Giai đoạn 1: Plan & Impact Analysis (Lập kế hoạch & Đánh giá tác động)

1. **Xác định mục tiêu & Phạm vi**:
   - Nếu yêu cầu người dùng chưa rõ ràng ➔ Kết hợp `skill(name="spec-driven")` để làm rõ yêu cầu trước.
   - Liệt kê danh sách tất cả các module/file sẽ cần tạo mới hoặc chỉnh sửa.
2. **Phân tích tác động (Impact Analysis)**:
   - Dùng `grep` để tìm tất cả các thành phần phụ thuộc vào các module sắp sửa.
   - Nhận diện các điểm nhạy cảm: Có đụng vào auth, database migration, config production, payment logic, CI/CD không? (Nếu có ➔ Dùng `question` xác nhận trước).
3. **Lập Task List**:
   - Sử dụng `todowrite` để chia nhỏ nhiệm vụ thành các bước tuần tự rõ ràng (3–6 đầu việc).

## 2. Giai đoạn 2: Implementation Order (Thứ tự thực thi)

Thực hiện theo nguyên tắc **Xây nền móng trước, tích hợp sau**:

```
[1. Core / Data Models / Utils]
             ↓
[2. Business Logic / Services]
             ↓
[3. Controllers / Handlers / API]
             ↓
[4. UI / CLI Presentation Layer]
```

- **Mỗi file 1 thao tác tập trung**: Lập kế hoạch tất cả thay đổi trong file, rồi thực hiện qua 1 lệnh `edit` hoặc `multiedit` duy nhất.
- **Cập nhật Todo**: Cập nhật tiến độ qua `todowrite` tại các mốc quan trọng (~50%, khi hoàn thành hoặc khi có thay đổi scope). Không gọi `todowrite` sau mỗi bước nhỏ.

## 3. Giai đoạn 3: Tích hợp & Verification

- Chạy test / linter ở từng module sau khi hoàn thành, không dồn toàn bộ lỗi về cuối cùng mới sửa.
- Dùng `grep` rà soát lại toàn bộ codebase đảm bảo không còn logic cũ hoặc import lỗi thời sót lại.
- Tóm tắt ngắn gọn các file đã thay đổi, các rủi ro còn lại và hướng dẫn chạy cho người dùng.
