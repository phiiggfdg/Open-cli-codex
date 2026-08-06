---
name: canva
description: Thiết kế presentation và visual UI hoàn thiện để nhập vào Canva dưới dạng PPTX chỉnh sửa được. Dùng khi người dùng yêu cầu Canva, Canva presentation, thiết kế slide/UI, pitch deck, social deck hoặc file PPTX thiên về thẩm mỹ. Nếu brief còn thiếu, hỏi ngắn gọn để chốt ý tưởng và hướng hình ảnh; nếu brief đã đủ, tóm tắt hướng thiết kế rồi gọi skill powerpoint của dự án để tạo và kiểm tra PPTX.
---

# Canva-ready UI bằng PPTX

Tạo thiết kế có chủ đích, đẹp khi trình chiếu và vẫn dễ chỉnh sửa sau khi import vào Canva.

Đầu ra mặc định là `.pptx`.

Không tuyên bố:

- tạo được file `.canva`;
- điều khiển trực tiếp Canva;
- giữ nguyên hoàn toàn font, xuống dòng, animation hoặc transition sau khi import;
- đã kiểm tra trực tiếp trong Canva nếu chưa thật sự thực hiện.

Ưu tiên:

1. Nội dung rõ và dễ đọc.
2. Bố cục có chủ đích.
3. Các thành phần chính vẫn chỉnh sửa được.
4. Tương thích tốt khi import vào Canva.
5. Thiết kế đẹp nhưng không lấn át nội dung.
6. Minimum code và minimum complexity giải quyết đúng yêu cầu.

---

## Bắt buộc hiểu brief trước

Không bắt đầu dựng toàn bộ file khi chưa hiểu đủ ý tưởng của người dùng.

Nếu brief còn thiếu, hỏi một câu ngắn, gom các ý quan trọng:

- nội dung, mục tiêu và người xem;
- loại thiết kế và số trang dự kiến;
- phong cách, màu sắc, thương hiệu hoặc mẫu tham khảo;
- tài sản sẵn có như logo, ảnh, font và dữ liệu;
- tỷ lệ khung hình;
- nền tảng sử dụng chính;
- mức độ chỉnh sửa mong muốn sau khi import.

Mặc định cho presentation:

- tỷ lệ `16:9`;
- nội dung ưu tiên đọc tốt trên màn hình;
- file đầu ra là `.pptx`;
- các thành phần chính dùng text, shape, picture và chart native.

Không hỏi lại thông tin người dùng đã cung cấp rõ.

Nếu brief đã đủ và người dùng yêu cầu làm ngay:

1. Tóm tắt hướng thiết kế ngắn gọn.
2. Không hỏi thêm chỉ để kéo dài quy trình.
3. Gọi skill `powerpoint`.
4. Triển khai.

Nếu người dùng chưa có phong cách, đưa tối đa ba hướng cụ thể để họ chọn:

1. **Editorial cao cấp**  
   Chữ lớn, ảnh mạnh, nhiều khoảng thở, màu trung tính với một màu nhấn.

2. **Modern tech**  
   Lưới chính xác, tương phản sáng tối, gradient tiết chế, chi tiết sắc gọn.

3. **Playful brand**  
   Màu nổi, hình khối mềm, typography giàu cá tính và nhịp bố cục linh hoạt.

Không đưa quá nhiều lựa chọn khiến người dùng khó quyết định.

---

## Chốt hướng thiết kế

Trước khi dựng nhiều trang, mô tả ngắn thiết kế dự kiến:

- concept trong một câu;
- bảng màu;
- cặp font;
- key visual hoặc ngôn ngữ hình ảnh;
- hệ lưới;
- lề và khoảng cách;
- nhịp chuyển giữa các trang;
- skeleton nội dung theo từng trang.

Với yêu cầu mơ hồ hoặc deck dài:

- xin xác nhận concept và skeleton trước;
- có thể dựng một trang đại diện hoặc style frame trước;
- sau khi chốt mới nhân hệ thống sang phần còn lại.

Chỉ xin xác nhận style frame khi:

- brief còn mơ hồ;
- deck dài;
- có nhận diện thương hiệu nhạy cảm;
- người dùng yêu cầu duyệt từng giai đoạn;
- sai hướng thiết kế sẽ gây nhiều công sửa lại.

Với task nhỏ và brief rõ:

- không dừng giữa chừng chỉ để xin xác nhận hình thức;
- tóm tắt hướng thiết kế rồi triển khai luôn.

---

## Chuẩn UI hoàn thiện

Một thiết kế hoàn thiện phải trông như sản phẩm đã được art-direct, không phải template mới điền chữ.

Yêu cầu:

- Có một tiêu điểm thị giác rõ trên mỗi trang.
- Hệ phân cấp đọc được ngay:
  - tiêu đề;
  - thông tin chính;
  - bằng chứng;
  - chi tiết phụ.
- Căn lề, baseline, khoảng cách và kích thước lặp lại nhất quán.
- Màu, font, bo góc, nét và phong cách ảnh thuộc cùng một hệ thống.
- Key visual đủ mạnh.
- Không dùng icon nhỏ hoặc các hộp rời rạc để thay thế hình ảnh chủ đạo.
- Mật độ cân bằng.
- Không nhồi chữ.
- Không để khoảng trống vô chủ đích.
- Các trang liền nhau có nhịp và silhouette khác nhau nhưng vẫn cùng một ngôn ngữ.
- Không biến mọi trang thành dashboard hoặc lưới card.
- Luân phiên có chủ đích giữa:
  - hero;
  - split layout;
  - editorial;
  - timeline;
  - quote;
  - comparison;
  - data;
  - full-bleed visual;
  - exercise;
  - summary.

Không dùng nhiều layout khác nhau chỉ để chứng minh sự đa dạng. Mỗi thay đổi bố cục phải phục vụ nội dung.

---

## Quản lý mật độ và không gian

Không thu nhỏ chữ chỉ để nhét đủ nội dung.

Khi nội dung quá dài, ưu tiên theo thứ tự:

1. Cô đọng câu chữ nhưng giữ nguyên ý.
2. Chia nội dung thành nhiều slide.
3. Chuyển chi tiết phụ sang speaker notes.
4. Dùng phụ lục nếu phù hợp.
5. Hỏi người dùng nếu cần lược bỏ nội dung quan trọng.

Không tự cắt mất dữ kiện, điều kiện, con số hoặc ý chính mà không báo.

Không đặt nội dung dưới:

- header;
- footer;
- tab;
- navigation rail;
- logo lớn;
- số trang;
- decoration cố định;
- vùng an toàn dành cho ảnh hoặc key visual.

Mỗi slide phải có một vùng nội dung chính rõ ràng và đủ khoảng thở.

Không dùng quá nhiều trên cùng một slide:

- lớp nền;
- khung;
- card;
- badge;
- border;
- shadow;
- icon;
- nhãn nhỏ;
- thanh điều hướng giả lập.

Không để UI chrome bóp nghẹt vùng nội dung.

---

## Header, footer và UI chrome

`UI chrome` là các thành phần lặp lại như:

- header;
- footer;
- logo;
- số trang;
- tab;
- thanh điều hướng;
- rail;
- đường viền;
- nhãn section;
- decoration cố định.

Quy tắc:

- Chrome chỉ hỗ trợ nhận diện và định hướng.
- Chrome không được trở thành tiêu điểm của mọi slide.
- Header và footer phải tiết chế.
- Không để thanh tiêu đề quá dày.
- Không đặt navigation bar giả lập trên mọi slide nếu không phục vụ nội dung.
- Không để số trang hoặc badge chiếm diện tích đáng kể.
- Với slide dày nội dung, giảm hoặc bỏ chrome không cần thiết.
- Với slide hero, chrome có thể tối giản hoặc ẩn hoàn toàn.
- Không đặt nội dung sát chrome đến mức tạo cảm giác bị ép.
- Không để chrome chồng lên text, hình ảnh, chart hoặc vùng tương tác.

Nếu một thành phần lặp lại không giúp người xem hiểu slide tốt hơn, loại bỏ nó.

---

## Typography

Ưu tiên kích thước chữ tối thiểu cho presentation `16:9`:

- tiêu đề deck: `50 pt`;
- tiêu đề trang: `35 pt`;
- tiêu đề phụ: `24 pt`;
- nội dung: `16 pt`;
- chú thích phụ: không nhỏ hơn mức vẫn đọc được trên thiết bị đích.

Chỉ giảm kích thước khi thật sự cần và vẫn đọc tốt trên điện thoại.

Quy tắc:

- Tránh tiêu đề hai dòng nếu có thể.
- Không ép tiêu đề một dòng bằng cách thu nhỏ quá mức.
- Dùng font phổ biến hoặc font người dùng xác nhận có trên Canva.
- Không phụ thuộc vào font hiếm.
- Dự kiến khả năng font fallback.
- Không dùng quá nhiều font trong một deck.
- Thông thường chỉ cần:
  - một font display;
  - một font body;
  - hoặc một font family có nhiều weight.
- Giữ line height và paragraph spacing nhất quán.
- Không dùng chữ in hoa dài cho nội dung chính.
- Không dùng quá nhiều weight, màu hoặc kiểu nhấn trong một đoạn.
- Không đặt text sát mép shape hoặc mép slide.

Các mốc kích thước trên là mặc định cho presentation `16:9`.

Với:

- social deck;
- mobile-first layout;
- tài liệu dày thông tin;
- poster;
- infographic;
- màn hình dọc;

có thể điều chỉnh, nhưng phải kiểm tra ở kích thước sử dụng thực tế.

---

## Slide song ngữ

Với slide có hai ngôn ngữ:

- Phân cấp rõ ngôn ngữ chính và bản dịch.
- Không để hai ngôn ngữ cạnh tranh thị giác ngang nhau nếu gây rối.
- Giữ cách trình bày nhất quán giữa các slide.
- Có thể dùng:
  - khác weight;
  - khác kích thước;
  - khác màu nhẹ;
  - khoảng cách rõ;
  - cột riêng;
  - dòng dịch bên dưới.
- Không lặp toàn bộ nội dung hai lần trong cùng một khối nếu làm slide quá dày.
- Không giảm font quá nhỏ chỉ để chứa cả hai bản.
- Với nội dung dài, ưu tiên:
  - ngôn ngữ chính trên slide;
  - bản dịch ngắn hơn;
  - chi tiết bổ sung trong notes hoặc phụ lục.

---

## Hình ảnh và key visual

Ảnh phải hỗ trợ nội dung, không chỉ dùng để lấp khoảng trống.

Yêu cầu:

- Ảnh đủ độ phân giải.
- Không kéo méo ảnh.
- Crop có chủ đích.
- Giữ chủ thể quan trọng trong vùng an toàn.
- Không che mặt, chữ hoặc chi tiết chính.
- Không dùng ảnh có watermark ngoài chủ đích.
- Không dùng asset chưa xác minh nguồn hoặc URL.
- Không dùng quá nhiều phong cách ảnh trong cùng một deck.
- Giữ nhất quán:
  - ảnh chụp;
  - minh họa;
  - 3D;
  - collage;
  - icon;
  - line art.

Key visual phải đủ mạnh để tạo nhận diện.

Không dùng nhiều icon nhỏ thay cho một visual chính nếu nội dung cần cảm xúc hoặc bối cảnh.

Nếu không có ảnh phù hợp:

- dùng shape native có chủ đích;
- dùng typography làm key visual;
- dùng diagram đơn giản;
- dùng placeholder rõ ràng khi asset bắt buộc còn thiếu.

Không bịa URL ảnh, icon, font hoặc CDN.

---

## Chart và dữ liệu

Chart phải giúp hiểu dữ liệu nhanh hơn.

Quy tắc:

- Không tạo chart nếu một con số lớn hoặc câu ngắn đã truyền đạt tốt hơn.
- Không dùng quá nhiều loại chart trong cùng một deck.
- Không dùng hiệu ứng 3D cho chart.
- Không dùng quá nhiều nhãn.
- Không để legend, gridline hoặc decoration lấn át dữ liệu.
- Giữ màu dữ liệu nhất quán giữa các slide.
- Chỉ nhấn màu cho dữ kiện quan trọng.
- Không thay đổi tỷ lệ trục gây hiểu nhầm.
- Nếu dữ liệu chưa đủ hoặc không rõ nguồn, không tự tạo số liệu giả.

Chart Canva-safe nên giữ đơn giản:

- column;
- bar;
- line;
- pie khi số nhóm ít;
- doughnut khi thật sự phù hợp;
- comparison chart đơn giản.

---

## Table

Bảng phải được dùng khi người xem cần đối chiếu chính xác.

Quy tắc:

- Không dùng bảng cho nội dung có thể trình bày rõ hơn bằng layout khác.
- Không nhồi quá nhiều cột.
- Không dùng font quá nhỏ.
- Hạn chế merge cell phức tạp.
- Giữ border đơn giản.
- Dùng fill và typography để tạo hierarchy.
- Không dùng mọi ô như một card độc lập.
- Kiểm tra bảng sau khi import vì Canva có thể thay cách xuống dòng.

---

## Khả năng chỉnh sửa trong Canva

Thiết kế theo nguyên tắc Canva-safe:

- text phải là text native;
- khối UI cơ bản dùng shape native;
- ảnh được nhúng;
- ảnh được crop đúng tỷ lệ;
- bảng giữ đơn giản;
- chart giữ đơn giản;
- không rasterize cả trang chỉ để giữ vẻ ngoài;
- không biến toàn bộ slide thành một ảnh nền;
- không phụ thuộc vào font hiếm;
- hạn chế merge phức tạp;
- hạn chế hiệu ứng 3D;
- hạn chế shadow đặc thù;
- hạn chế transparency phức tạp;
- hạn chế OOXML tùy biến;
- không dùng animation như phần bắt buộc để hiểu nội dung.

Có thể rasterize một thành phần riêng khi:

- thành phần đó không cần chỉnh sửa;
- việc giữ native gây lỗi nghiêm trọng;
- người dùng chấp nhận;
- không làm mất khả năng chỉnh sửa phần còn lại.

Không rasterize toàn bộ trang nếu chưa được người dùng yêu cầu rõ.

Canva có thể:

- thay font;
- thay cách xuống dòng;
- thay crop;
- thay vị trí nhẹ;
- bỏ animation;
- bỏ transition;
- render shadow hoặc transparency khác;
- xử lý chart và table khác PowerPoint.

Nếu người dùng cần chuyển động:

- mô tả motion plan theo từng trang;
- chỉ rõ phần tử nào xuất hiện trước;
- chỉ rõ hiệu ứng gợi ý trong Canva;
- không hứa animation PowerPoint sẽ được giữ nguyên sau import.

---

## Motion plan cho Canva

Khi người dùng yêu cầu animation hoặc motion nhưng đầu ra vẫn là PPTX Canva-ready:

- Không phụ thuộc vào animation để truyền đạt nội dung cốt lõi.
- Tạo slide tĩnh vẫn hiểu được đầy đủ.
- Có thể cung cấp motion plan ngắn.

Ví dụ motion plan:

- Title: fade in.
- Key visual: rise hoặc pan nhẹ.
- Bullet: appear lần lượt.
- Data highlight: pop hoặc wipe.
- Transition giữa section: dissolve hoặc match and move nếu Canva hỗ trợ.

Không tạo motion plan dài dòng nếu người dùng không yêu cầu.

---

## Style frame và design tokens

Trước khi dựng toàn bộ deck dài, có thể tạo một style frame đại diện.

Style frame nên thể hiện:

- title;
- body text;
- màu nền;
- màu nhấn;
- card hoặc shape chính;
- treatment ảnh;
- icon;
- header hoặc footer;
- khoảng cách;
- cách trình bày dữ liệu.

Sau khi chốt, tái sử dụng design tokens:

- màu;
- font;
- font size;
- font weight;
- lề;
- spacing;
- radius;
- line width;
- shadow;
- opacity;
- image treatment;
- grid.

Không biến design tokens thành một framework lớn nếu chỉ tạo một deck nhỏ.

Chỉ tạo helper hoặc cấu trúc dùng lại khi nó giúp code ngắn và nhất quán hơn.

---

## Quy trình thực hiện

1. Đọc yêu cầu.
2. Kiểm tra brief đã đủ chưa.
3. Nếu thiếu, hỏi một câu ngắn để chốt các điểm quan trọng.
4. Nếu brief đã đủ, tóm tắt hướng thiết kế.
5. Tạo design brief ngắn.
6. Tạo skeleton trang.
7. Nếu task lớn hoặc phạm vi chưa rõ, gọi `skill(name="spec-driven")`.
8. Gọi `skill(name="powerpoint")` trước khi viết mã hoặc chỉnh PPTX.
9. Dùng hướng dẫn trong skill `powerpoint` để triển khai bằng `python-pptx`.
10. Không sao chép hoặc tạo một runtime PPTX khác.
11. Dựng style frame nếu task cần duyệt hướng.
12. Tạo design tokens tối thiểu.
13. Dựng từng trang theo skeleton.
14. Trang mới kế thừa hệ thống thị giác nhưng không lặp nguyên bố cục.
15. Dùng API public của `python-pptx` trước.
16. Hạn chế OOXML tùy biến để giữ khả năng import Canva.
17. Chạy script tạo file.
18. Lưu file.
19. Mở lại bằng `Presentation(output_path)`.
20. Render hoặc preview khi môi trường cho phép.
21. Kiểm tra tổng thể.
22. Sửa lỗi.
23. Chỉ giao file sau khi verify phù hợp.

---

## Kiểm tra preview

Khi môi trường cho phép:

### Kiểm tra toàn bộ deck ở thumbnail

Dùng để đánh giá:

- nhịp tổng thể;
- sự nhất quán;
- mức độ đa dạng layout;
- phân bố màu;
- density;
- slide nào quá nặng hoặc quá trống;
- chrome có chiếm quá nhiều không;
- deck có bị lặp card hay không.

Thumbnail không đủ để xác nhận:

- text không tràn;
- text không đè;
- baseline đúng;
- crop ảnh chính xác;
- font đủ lớn;
- khoảng cách nhỏ đã chuẩn.

### Kiểm tra từng slide ở kích thước đầy đủ

Dùng để phát hiện:

- text overflow;
- overlap;
- crop sai;
- chữ quá nhỏ;
- lệch căn;
- khoảng cách không đều;
- shape nằm ngoài slide;
- contrast thấp;
- header hoặc footer đè nội dung;
- visual bị cắt;
- bảng hoặc chart khó đọc.

Không dùng một ảnh collage nhỏ làm bằng chứng duy nhất rằng deck đã sạch.

Nếu không thể render:

- vẫn phải reopen bằng `python-pptx`;
- kiểm tra vị trí và kích thước shape bằng code nếu cần;
- nêu rõ chưa kiểm tra trực quan đầy đủ.

---

## Kiểm tra overflow và overlap

Trước khi giao:

- kiểm tra text box có đủ chiều cao;
- không đặt text quá sát mép;
- không để title đè subtitle;
- không để body đè footer;
- không để hình đè text ngoài chủ đích;
- không để chart đè legend;
- không để bảng vượt vùng an toàn;
- không để object nằm ngoài slide;
- không để chrome lấn vào content area.

Nếu nội dung không vừa:

1. Rút gọn.
2. Chia slide.
3. Tăng vùng nội dung.
4. Giảm decoration.
5. Chỉ giảm font trong giới hạn đọc được.

Không ưu tiên giảm font ngay từ đầu.

---

## Quy tắc nội dung

Không tự thêm nội dung ngoài yêu cầu chỉ để lấp slide.

Không tạo:

- số liệu giả;
- trích dẫn giả;
- nguồn giả;
- logo giả;
- testimonial giả;
- tên khách hàng giả;
- biểu đồ không có dữ liệu;
- case study không có bằng chứng.

Nếu thiếu nội dung:

- hỏi người dùng;
- dùng placeholder rõ ràng;
- tạo skeleton;
- ghi rõ phần cần bổ sung.

Có thể biên tập câu chữ để ngắn và rõ hơn, nhưng không làm thay đổi ý nghĩa.

---

## Simplicity First

Minimum design và minimum code giải quyết đúng yêu cầu.

Không:

- tạo framework presentation tổng quát;
- tạo design system khổng lồ cho một deck nhỏ;
- tạo class khi vài helper đơn giản đã đủ;
- thêm nhiều theme;
- thêm nhiều phương án không ai yêu cầu;
- thêm animation chỉ để trang trí;
- tạo hàng loạt file probe;
- tạo abstraction chỉ dùng một lần;
- nhồi UI để chứng minh khả năng thiết kế;
- dùng quá nhiều card, badge, icon hoặc decoration;
- viết hàng trăm dòng cho một hiệu ứng nhỏ có thể bỏ.

Tự hỏi:

> Một senior designer hoặc senior engineer có cho rằng giải pháp này quá phức tạp so với yêu cầu không?

Nếu có, đơn giản hóa.

---

## Checklist trước khi giao

### Nội dung

- Đúng mục tiêu.
- Đúng người xem.
- Đúng số trang.
- Đúng thứ tự.
- Không còn nội dung mẫu ngoài chủ ý.
- Không có thông tin giả.
- Nội dung dài đã được xử lý hợp lý.
- Không có slide phải dùng chữ quá nhỏ chỉ để chứa đủ nội dung.

### Bố cục

- Đúng tỷ lệ khung hình.
- Không có text overflow.
- Không có overlap ngoài chủ đích.
- Không có phần tử nằm ngoài slide.
- Không có vùng nội dung bị chrome bóp nghẹt.
- Header, footer, logo và số trang không lấn át nội dung.
- Mỗi slide có tiêu điểm rõ.
- Khoảng trắng có chủ đích.
- Không lặp cùng một layout quá nhiều.

### Typography

- Font nhất quán.
- Kích thước đọc được.
- Line height hợp lý.
- Không có tiêu đề bị ép hoặc xuống dòng xấu.
- Bản song ngữ có phân cấp rõ.
- Không phụ thuộc vào font hiếm ngoài chủ đích.

### Hình ảnh

- Ảnh đủ nét.
- Crop hợp lý.
- Không méo.
- Không che chủ thể.
- Không có watermark ngoài chủ đích.
- Phong cách hình ảnh nhất quán.

### Màu sắc

- Độ tương phản đủ.
- Màu nhấn có chủ đích.
- Không dùng quá nhiều màu.
- Dữ liệu dùng màu nhất quán.
- Nội dung vẫn hiểu được nếu một số hiệu ứng bị mất.

### Canva editability

- Text chính là text native.
- Shape chính là shape native.
- Không rasterize toàn bộ trang ngoài yêu cầu.
- Bảng và chart đủ đơn giản.
- Không phụ thuộc vào OOXML đặc thù.
- Các phần tử chính vẫn chỉnh sửa được sau import.

### Verify

- File đã save thành công.
- File đã reopen thành công bằng `python-pptx`.
- Deck đã được kiểm tra ở thumbnail nếu có thể.
- Từng slide đã được kiểm tra ở kích thước đầy đủ nếu có thể.
- Đã sửa lỗi overflow, overlap, crop, contrast và spacing.
- Nêu rõ phần chưa thể xác minh trực tiếp trong Canva hoặc PowerPoint thật.

---

## Giao file

Khi giao file, tóm tắt ngắn:

- concept;
- tỷ lệ;
- số trang;
- phong cách;
- mức độ editable;
- asset đã dùng;
- mức verify đã thực hiện;
- giới hạn chưa xác minh.

Hướng dẫn nhập Canva:

1. Mở Canva.
2. Chọn **Import file**.
3. Tải file `.pptx` lên.
4. Rà lại:
   - font;
   - xuống dòng;
   - crop ảnh;
   - chart;
   - table;
   - animation;
   - transition.
5. Thay font hoặc motion trong Canva nếu cần.

Không tuyên bố file sẽ giữ nguyên tuyệt đối sau import.

Cách báo phù hợp:

> File đã được thiết kế theo hướng Canva-safe, với text và shape chính vẫn chỉnh sửa được. File đã lưu và mở lại thành công bằng python-pptx. Sau khi import vào Canva, cần rà lại font, xuống dòng, crop và animation vì Canva có thể render khác PowerPoint.