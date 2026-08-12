---
name: testing
description: Viết test có chủ đích — chọn đúng loại test, đúng case đáng test, tránh test giả tạo chỉ để pass. Dùng khi user yêu cầu viết test, khi task thêm logic mới cần test đi kèm, hoặc khi review phát hiện thiếu test cho code quan trọng. Không khóa framework — áp dụng cho pytest, Jest, JUnit, hay bất kỳ test runner nào project đang dùng.
---

# Testing có chủ đích

Simplicity First vẫn áp dụng cho test: **test đáng viết, không phải test
cho có.** Một test giả tạo (assert luôn đúng, mock che hết logic thật, test
chỉ gọi hàm không kiểm tra gì) tệ hơn không có test — nó tạo cảm giác an
toàn giả.

## 1. Chọn loại test theo rủi ro, không theo thói quen

- **Unit test**: logic thuần, ít phụ thuộc ngoài (hàm tính toán, transform
  dữ liệu, validation, business rule). Nhanh, cô lập, nên là phần lớn test
  suite.
- **Integration test**: chỗ nhiều thành phần ghép lại có khả năng sai dù
  từng phần đúng riêng lẻ — API endpoint gọi qua nhiều layer, DB query thật,
  luồng auth. Chậm hơn unit test, không cần phủ mọi nhánh, chỉ cần phủ
  đường đi chính và điểm nối quan trọng.
- **E2E test**: chỉ khi luồng người dùng thật sự quan trọng và có khả năng
  vỡ do thay đổi ở nhiều layer cùng lúc (checkout, login, luồng thanh toán).
  Đắt để viết và maintain — không lạm dụng cho mọi tính năng.
- Không viết integration/E2E test cho thứ unit test đã phủ đủ — tốn thời
  gian chạy và maintain mà không tăng độ tin cậy tương ứng.

## 2. Case nào đáng test

Ưu tiên theo thứ tự:

1. **Business logic quan trọng** — tính tiền, phân quyền, trạng thái
   chuyển đổi (state machine), bất kỳ chỗ nào sai sẽ gây hậu quả thật.
2. **Edge case thực tế** — input rỗng, giá trị biên (0, âm, max), dữ liệu
   thiếu field, encoding lạ — không phải edge case tưởng tượng không bao
   giờ xảy ra trong thực tế sử dụng.
3. **Bug đã từng xảy ra** — mỗi bug fix nên có 1 test tái hiện đúng bug đó,
   để nó không quay lại (regression test) — đây là ROI cao nhất trên mỗi
   test viết ra.
4. **Nhánh rẽ có hậu quả khác nhau rõ rệt** — if/else dẫn tới hành vi khác
   nhau đáng kể, không phải mọi if/else đều cần test riêng nếu hậu quả sai
   là tầm thường.

Không cần test:

- Code chỉ gọi thẳng thư viện chuẩn không có logic thêm (getter/setter
  trần, wrapper 1-dòng không biến đổi gì).
- Config, constant, hoặc code không có nhánh rẽ logic nào.
- UI thuần hiển thị không có logic tính toán (test bằng visual/manual
  verification hợp lý hơn, xem `skill(name="frontend-work")`).

## 3. Tránh test giả tạo

Dấu hiệu một test không có giá trị thật:

- **Assert luôn đúng bất kể code sai** — ví dụ chỉ kiểm tra hàm không
  throw exception mà không kiểm tra giá trị trả về đúng.
- **Mock quá sâu** — mock hết cả phần logic đang muốn test, chỉ còn lại
  kiểm tra "hàm mock có được gọi" thay vì kiểm tra hành vi thật.
- **Test phụ thuộc thứ tự chạy** hoặc trạng thái global còn sót từ test
  trước — test phải chạy độc lập, chạy riêng lẻ cũng phải pass.
- **Snapshot test không ai review** — chấp nhận mọi thay đổi output mà
  không ai đọc lại xem thay đổi đó có đúng ý hay không, chỉ để xanh CI.
- **Viết test sau khi biết code sai để né sửa** — sửa test cho khớp hành vi
  sai thay vì sửa code là lừa dối bản thân, không phải test.

Một test tốt phải **fail được khi code sai** — trước khi coi 1 test là
xong, thử hình dung (hoặc thực sự thử) phá code đi 1 chút xem test có bắt
được không. Nếu test vẫn xanh dù logic sai, test đó vô giá trị.

## 4. Đặt tên và cấu trúc

- Tên test mô tả rõ hành vi đang kiểm tra và điều kiện, không phải tên
  chung chung (`test_function_works` → thay bằng mô tả tình huống + kết
  quả mong đợi, ví dụ "trả về rỗng khi input rỗng").
- Structure rõ 3 phần: setup (arrange), hành động (act), kiểm tra (assert)
  — dù không cần comment tường minh, giữ thứ tự này giúp test dễ đọc.
- Một test kiểm tra một hành vi. Nhiều assert không liên quan trong cùng 1
  test khiến khó biết chính xác cái gì hỏng khi test fail.

## 5. Khi nào dừng viết thêm test

- Đủ khi các case rủi ro cao (mục 2) đã phủ — không cần chạy theo % coverage
  tuyệt đối, con số coverage cao không đồng nghĩa test có giá trị.
- Nếu task nhỏ, rủi ro thấp, thời gian không cho phép — nói rõ phạm vi đã
  test và phần nào chưa, để user tự quyết có cần thêm hay không, thay vì
  âm thầm bỏ qua.

## Framework

Không khóa vào 1 framework cụ thể. Dùng đúng test runner project đang có
sẵn (pytest, unittest, Jest, Vitest, JUnit, Go testing...) — nguyên tắc
trên là về cách chọn/viết test, không phải cú pháp assert của framework
nào.
