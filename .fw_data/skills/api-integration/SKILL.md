---
name: api-integration
description: Tích hợp REST/GraphQL/SDK bên thứ ba đúng cách — đọc docs trước khi đoán field, xử lý auth/rate-limit/retry/lỗi, không tự bịa response shape. Dùng khi task gọi API ngoài (provider AI, thanh toán, cloud service, MCP server...) mà agent chưa xác nhận rõ contract thật.
---

# API integration

Lỗi phổ biến nhất: **đoán field/response shape từ trí nhớ hoặc từ API tương
tự đã biết**, rồi code chạy được nhưng sai ngay khi gặp response thật. Skill
này ép việc xác nhận contract thật trước khi code, không phải dạy cú pháp
HTTP client.

## 1. Xác nhận contract trước khi code

- Không tự bịa tên field, response shape, mã lỗi, hay endpoint path từ trí
  nhớ — kể cả với API quen thuộc (OpenAI, AWS, Stripe...), vì version/field
  có thể đã đổi so với lúc training. Tra docs thật (`websearch`/`webfetch`)
  hoặc đọc code/type definition đã có sẵn trong project trước khi viết.
- Nếu project đã có SDK/client library cho API đó, đọc type definition hoặc
  code mẫu đã dùng trong project trước — đáng tin hơn docs ngoài vì khớp
  đúng version đang cài.
- Nếu không tra được docs (không có mạng, docs không rõ) và không có code
  mẫu trong project, nói rõ đang giả định field nào, đề nghị test bằng 1
  request thật trước khi tích hợp sâu — không lặng lẽ code tiếp trên giả
  định.
- Với GraphQL: lấy schema thật (introspection hoặc file `.graphql` có sẵn)
  trước khi viết query — không đoán field name theo REST tương tự.

## 2. Auth

- Xác định đúng kiểu auth API yêu cầu (API key header, OAuth token, HMAC
  signature, mTLS...) từ docs — không giả định "chắc giống API khác".
- Không hardcode secret/token/API key trong code. Đọc từ biến môi trường
  hoặc config đã có sẵn trong project; nếu chưa có, hỏi user muốn lưu ở
  đâu thay vì tự chọn.
- Với token có thời hạn (OAuth access token, session token), xử lý refresh
  trước khi hết hạn hoặc bắt lỗi 401 để refresh — không giả định token
  sống mãi.
- Không log token/key ra console hoặc file log, kể cả khi debug.

## 3. Rate limit & retry

- Đọc rate limit thật từ docs (số request/giây, quota theo phút/ngày) trước
  khi thiết kế tần suất gọi — không đoán số tùy tiện.
- Retry chỉ với lỗi có khả năng tạm thời (timeout, 429, 5xx) — không retry
  lỗi do request sai (400, 401, 403, 404), vì retry không sửa được nguyên
  nhân và có thể khiến vấn đề tệ hơn (spam log, tốn quota).
- Dùng exponential backoff cho retry, có giới hạn số lần thử — tránh vòng
  lặp gọi API vô hạn khi lỗi kéo dài (đối chiếu Anti-loop trong system
  prompt).
- Nếu API trả header rate-limit (`Retry-After`, `X-RateLimit-Remaining`...),
  đọc và tôn trọng nó thay vì tự đoán thời gian chờ.
- Với API tính phí theo request, cân nhắc rõ với user trước khi viết code
  gọi API trong vòng lặp lớn hoặc test lặp lại nhiều lần.

## 4. Xử lý lỗi và response

- Không giả định response luôn thành công và luôn đúng shape — luôn kiểm
  tra status code / field báo lỗi trước khi parse dữ liệu thành công.
- Phân biệt lỗi theo mã: lỗi do request (4xx, thường không tự sửa được,
  cần báo user hoặc dừng), lỗi tạm thời (429, 5xx, có thể retry), lỗi
  không xác định (parse thất bại, timeout — log rõ và không tự đoán vì sao).
- Không nuốt lỗi (catch rồi bỏ qua im lặng) — nếu chủ động không muốn lỗi
  làm gián đoạn luồng chính, phải log/báo rõ ràng, không âm thầm coi như
  thành công.
- Validate response shape trước khi dùng field sâu bên trong (field có thể
  null/thiếu tùy trạng thái) — tránh lỗi runtime khi field không tồn tại
  thay vì kiểm tra trước.

## 5. Test tích hợp

- Test với ít nhất 1 request thật (hoặc sandbox/staging environment nếu
  API có) trước khi coi tích hợp là xong — không chỉ dựa vào việc code
  biên dịch/chạy không lỗi cú pháp.
- Với case cần mock (unit test phần logic xử lý response), mock dựa trên
  response thật đã quan sát được, không bịa cấu trúc — xem thêm
  `skill(name="testing")` cho nguyên tắc test nói chung.
- Test case lỗi thường bị bỏ qua: rate limit, timeout, response rỗng/thiếu
  field, mất kết nối giữa chừng — đáng test hơn happy path vì đây là nơi
  code thật hay vỡ trong production.

## Công nghệ

Không khóa vào 1 HTTP client hay ngôn ngữ cụ thể. Áp dụng cho REST, GraphQL,
gRPC, hay SDK chính thức của provider (Anthropic SDK, AWS SDK, Stripe SDK,
MCP client...) — nguyên tắc trên là về cách xác nhận contract và xử lý lỗi/
auth/rate-limit, không phải cú pháp gọi request của thư viện nào.
