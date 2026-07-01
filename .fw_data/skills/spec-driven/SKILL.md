# Spec-driven thinking

Dùng khi task đủ lớn/mơ hồ để việc "hiểu sai ý định" tốn nhiều công hơn việc dừng lại
làm rõ trước. Đây không phải form để điền — chỉ là 4 câu hỏi nên tự trả lời được
(hoặc hỏi user nếu không) trước khi bắt đầu sửa code trên diện rộng.

## 1. Mục tiêu thật là gì, không phải yêu cầu bề mặt

Người dùng nói "thêm X" — nhưng vấn đề họ đang cố giải quyết có thể rộng/hẹp hơn X.
Nếu implement đúng nghĩa đen mà không hỏi, có tạo ra thứ họ không dùng được không?

## 2. Ranh giới: cái gì KHÔNG làm

Task lớn thường phình ra vì không ai nói rõ điểm dừng. Trước khi code, tự hỏi:
phần nào của việc này rõ ràng ngoài phạm vi yêu cầu, dù có vẻ "tiện làm luôn"?
Ghi nhận ra ngoài phạm vi = tín hiệu tốt, không phải thiếu sót.

## 3. Case biên nào sẽ phá hỏng cách làm đơn giản nhất

Không cần liệt kê hết — chỉ cần 2-3 case thực tế nhất có khả năng xảy ra
(dữ liệu rỗng, race condition, file không tồn tại, quyền bị từ chối, model/provider
không hỗ trợ...). Nếu case biên đó thay đổi kiến trúc giải pháp, tốt hơn nên biết
trước khi viết dòng code đầu tiên.

## 4. Cách nào biết là đã làm đúng

Không cần bộ test hình thức — chỉ cần 1 câu trả lời được: "chạy lệnh/thao tác gì
để biết tính năng này hoạt động đúng như mong đợi?" Nếu không trả lời được câu này,
có thể mục tiêu ở bước 1 vẫn còn mơ hồ.

---

## Khi nào bỏ qua bước này

- Task rõ ràng, phạm vi hẹp, chỉ 1 file/1 vị trí — dừng lại suy nghĩ ở đây tốn thời
  gian hơn là giúp ích.
- Đã rõ owner cho từng câu hỏi trên (user đã trả lời sẵn trong yêu cầu ban đầu).

## Bẫy thường gặp khi áp dụng

- Biến 4 câu hỏi thành tài liệu dài — mục đích là suy nghĩ nhanh, không phải viết
  báo cáo. Vài dòng ngắn là đủ.
- Hỏi user tất cả 4 câu cùng lúc — chỉ hỏi phần thật sự chưa rõ, phần còn lại tự
  suy luận hợp lý rồi nói rõ giả định đang dùng.
- Áp dụng cứng nhắc cho mọi task — bước này chỉ có giá trị khi rủi ro hiểu sai thật
  sự cao (nhiều module, nhiều cách hiểu hợp lý, hoặc chi phí sửa sai lớn).
