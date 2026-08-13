---
name: design
description: Thiết kế visual/UI từ đầu khi chưa có design system sẵn có — chọn palette, typography, layout có chủ đích, tránh rơi vào 3 look mặc định mà AI hay tạo ra. Dùng khi task là tạo landing page, dashboard mới, brand mới, hoặc bất kỳ UI nào cần một identity riêng — không phải khi đang match design system có sẵn (đó là `frontend-work`) hoặc xuất ra Canva/PPTX (đó là `canva`).
---

# Design

Tiếp cận như một creative lead ở studio nhỏ, nơi mỗi client nhận một visual
identity không lẫn với ai khác. Client đã từng từ chối những đề xuất "nhìn
là biết template", và đang trả tiền cho một quan điểm rõ ràng: chọn palette,
typography, layout có chủ đích riêng cho đúng brief này, và dám lấy 1 rủi ro
thẩm mỹ thật sự có lý do.

## Bắt đầu từ nội dung thật

Nếu brief không nói rõ sản phẩm/chủ đề là gì, tự chốt trước khi thiết kế:
đặt tên 1 chủ đề cụ thể, đối tượng người dùng, và nhiệm vụ duy nhất của
trang. Nếu có ngữ cảnh về sở thích/dự án của user (từ hội thoại, project đã
biết), dùng nó làm gợi ý hướng đi. Chất liệu, công cụ, ngôn ngữ riêng của
chính thế giới chủ đề đó — không phải template chung — là nơi những lựa
chọn khác biệt thật sự đến từ.

## Nguyên tắc thiết kế

**Hero là 1 luận điểm, không phải 1 khuôn mẫu.** Mở đầu bằng thứ đặc trưng
nhất của chủ đề, dưới bất kỳ hình thức nào hợp lý: headline, ảnh, animation,
demo sống, một khoảnh khắc tương tác. "Số lớn + label nhỏ + số liệu phụ +
gradient accent" là câu trả lời khuôn mẫu — chỉ dùng nếu đó thực sự là lựa
chọn tốt nhất cho brief này, không phải vì quen tay.

**Typography mang tính cách của trang.** Ghép font display và body có chủ
đích, không phải cặp font mặc định dùng cho mọi project. Set type scale rõ
ràng với weight/width/spacing có chủ đích. Làm cho cách trình bày chữ trở
thành một phần đáng nhớ, không chỉ là phương tiện trung tính để hiển thị
nội dung.

**Structure là thông tin.** Các thiết bị cấu trúc (đánh số, eyebrow text,
divider, label) phải mã hóa một điều gì đó thật về nội dung, không phải để
trang trí. Đánh số kiểu 01/02/03 chỉ hợp lý nếu nội dung thực sự là một
chuỗi tuần tự (quy trình thật, timeline có thứ tự mang thông tin) — hỏi lại
xem lựa chọn đó có thật sự hợp lý trước khi dùng.

**Dùng motion có chủ đích.** Cân nhắc animation phục vụ đúng chủ đề ở đâu:
page-load sequence, scroll-reveal, hover micro-interaction, không khí nền.
Một khoảnh khắc được dàn dựng kỹ thường ấn tượng hơn nhiều hiệu ứng rải rác.
Nhưng đôi khi ít lại là nhiều — animation thừa dễ khiến thiết kế trông như
do AI tạo ra.

**Độ phức tạp khớp với định hướng.** Hướng maximalist cần thực thi cầu kỳ;
hướng minimal cần chính xác tuyệt đối về spacing, type, chi tiết. Sự tinh
tế nằm ở việc thực thi tốt đúng định hướng đã chọn, không phải ở số lượng
chi tiết.

**Cân nhắc kỹ nội dung chữ viết.** Brief thường không có copy thật — việc
viết copy là của mình. Copy tệ khiến thiết kế trông templated y như layout
tệ vậy. Xem phần "Viết copy trong design" bên dưới.

## Quy trình: brainstorm → khám phá → lên plan → tự phê bình → build → phê bình lại

**Hiệu chỉnh nhận thức trước:** thiết kế do AI tạo hiện nay hay dồn vào 3
look mặc định: (1) nền cream ấm (gần #F4F1EA) với serif display tương phản
cao và accent màu đất nung/terracotta; (2) nền gần đen với 1 accent xanh lá
acid hoặc đỏ vermilion nổi bật; (3) layout kiểu broadsheet với hairline
rule, border-radius = 0, cột dày đặc kiểu báo giấy. Cả 3 đều hợp lý cho một
số brief cụ thể, nhưng chúng là mặc định chứ không phải lựa chọn — xuất
hiện bất kể chủ đề là gì. Nếu brief đã chỉ rõ hướng thị giác, theo đúng
brief — lời brief luôn thắng, kể cả khi nó yêu cầu đúng 1 trong 3 look
trên. Nếu brief để trống 1 trục nào đó, đừng tiêu khoảng tự do đó vào 1
trong 3 mặc định trên.

Làm theo 2 lượt:

**Lượt 1 — brainstorm.** Xây một hệ token gọn dựa trên brief:
- **Color**: mô tả palette bằng 4-6 giá trị hex có tên gọi.
- **Type**: font cho 2+ vai trò (1 display face có cá tính, dùng tiết chế;
  1 body face bổ trợ; 1 utility face cho caption/data nếu cần).
- **Layout**: 1 concept bố cục, mô tả bằng câu văn ngắn + ASCII wireframe
  để so sánh phương án.
- **Signature**: 1 chi tiết riêng biệt mà trang này sẽ được nhớ tới, thể
  hiện đúng tinh thần brief.

**Lượt 2 — review trước khi build.** Đối chiếu lại plan vừa brainstorm với
brief: nếu phần nào đọc giống câu trả lời mặc định mình sẽ tạo cho bất kỳ
brief tương tự nào (thử hình dung 1 brief gần giống, xem có ra kết quả
giống nhau không) — sửa lại phần đó, ghi rõ đã sửa gì và vì sao. Chỉ sau
khi xác nhận plan đủ riêng biệt mới bắt đầu viết code, theo đúng plan đã
sửa, suy ra mọi quyết định màu/type từ đó.

Khi viết code, cẩn thận với CSS selector specificity — dễ tạo class triệt
tiêu lẫn nhau (ví dụ selector theo type như `.section` và selector theo
element như `.cta` cùng set padding/margin, ghi đè lẫn nhau ngoài ý muốn),
đặc biệt ở spacing giữa các section.

## Tiết chế và tự phê bình

Dồn sự táo bạo vào đúng 1 chỗ. Để signature element là điểm đáng nhớ duy
nhất, giữ mọi thứ xung quanh tiết chế và kỷ luật, cắt bỏ mọi trang trí
không phục vụ brief. Không dám lấy rủi ro cũng là một rủi ro. Build tới
một ngưỡng chất lượng không cần tuyên bố ra: responsive tới mobile, focus
state hiển thị rõ khi dùng bàn phím, tôn trọng `prefers-reduced-motion`.

Tự phê bình khi build — nếu môi trường cho phép chụp/xem lại kết quả
(`verify`), dùng nó để soi lại thay vì chỉ tin vào code. Ghi lại ngắn gọn
đã thử hướng nào nếu cần lặp lại nhiều pass, để không lặp lại đúng ý tưởng
cũ.

Ghi nhớ lời khuyên của Chanel: trước khi ra khỏi nhà, soi gương và bỏ bớt 1
món phụ kiện.

## Viết copy trong design

Chữ xuất hiện trong thiết kế vì 1 lý do: giúp dễ hiểu hơn, từ đó dễ dùng
hơn. Chữ là chất liệu thiết kế, không phải trang trí. Đưa cùng mức độ chủ
đích vào copy như đã đưa vào spacing và màu sắc. Trước khi viết bất kỳ dòng
nào, hỏi thiết kế cần nói gì, và cách nói nào giúp người dùng định hướng
tốt nhất trong trải nghiệm đó.

Viết từ phía người dùng cuối. Gọi tên sự vật theo cái người dùng điều khiển
và nhận ra, không theo cách hệ thống được xây dựng bên trong — người dùng
quản lý thông báo, không phải "webhook config". Mô tả một thứ làm gì bằng
lời đơn giản thay vì quảng cáo nó. Cụ thể luôn tốt hơn khôn khéo.

Dùng active voice làm mặc định. Một control nên nói đúng điều xảy ra khi
dùng nó: "Lưu thay đổi", không phải "Gửi". Một hành động giữ nguyên tên
xuyên suốt luồng — nút ghi "Xuất bản" thì toast xác nhận cũng phải nói
"Đã xuất bản". Từ vựng của giao diện chính là biển chỉ đường cho người
dùng — nhất quán là cách người ta học được đường đi trong sản phẩm.

Coi lỗi và trạng thái rỗng là cơ hội định hướng, không phải cơ hội thể hiện
cảm xúc. Giải thích rõ chuyện gì đã xảy ra và cách sửa, bằng giọng của giao
diện chứ không phải giọng của một con người đang xin lỗi — thông báo lỗi
không xin lỗi, và không bao giờ mơ hồ về việc gì đã xảy ra. Màn hình rỗng
là một lời mời hành động, không phải một khoảng trống bị bỏ quên.

Giữ giọng văn tự nhiên và có chủ đích: động từ đơn giản, không câu chữ thừa,
tông giọng khớp với brand và đối tượng. Mỗi thành phần chỉ làm đúng 1 việc
— label thì label, ví dụ thì minh họa, không có gì âm thầm làm 2 việc cùng
lúc.

## Liên hệ với các skill khác

- Nếu task là **match design system đã có sẵn** trong project thay vì tạo
  mới → dùng `skill(name="frontend-work")` thay vì skill này.
- Nếu output cuối cùng cần dạng **Canva-ready hoặc PPTX** → sau khi có
  hướng thiết kế từ skill này, chuyển sang `skill(name="canva")` để tạo
  file thực tế.
- Với scene 3D hoặc hệ có trạng thái hình học (không phải UI phẳng) →
  `skill(name="computer-graphics")`.
