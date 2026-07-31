---
name: canva
description: Thiết kế presentation và visual UI hoàn thiện để nhập vào Canva dưới dạng PPTX chỉnh sửa được. Dùng khi người dùng yêu cầu Canva, Canva presentation, thiết kế slide/UI, pitch deck, social deck hoặc file PPTX thiên về thẩm mỹ. Luôn hỏi ý tưởng và hướng hình ảnh trước khi thiết kế, sau đó dùng skill powerpoint của dự án để tạo và kiểm tra PPTX.
---

# Canva-ready UI bằng PPTX

Tạo thiết kế có chủ đích, đẹp khi trình chiếu và vẫn dễ chỉnh sửa sau khi import vào Canva.

Đầu ra mặc định là `.pptx`. Không tuyên bố tạo file `.canva`, điều khiển Canva trực tiếp hoặc giữ nguyên mọi animation của PowerPoint sau khi import.

## Bắt buộc hỏi ý tưởng trước

Không bắt đầu dựng toàn bộ file khi chưa hiểu ý tưởng của người dùng.

Nếu brief còn thiếu, hỏi một câu ngắn, gom các ý quan trọng:

- nội dung, mục tiêu và người xem;
- loại thiết kế và số trang dự kiến;
- phong cách, màu sắc, thương hiệu hoặc mẫu tham khảo;
- tài sản sẵn có như logo, ảnh, font và dữ liệu;
- tỷ lệ khung hình; mặc định presentation là `16:9`.

Nếu người dùng chưa có phong cách, đưa tối đa ba hướng cụ thể để họ chọn:

1. **Editorial cao cấp** — chữ lớn, ảnh mạnh, nhiều khoảng thở, màu trung tính có một màu nhấn.
2. **Modern tech** — lưới chính xác, tương phản sáng/tối, gradient tiết chế, chi tiết sắc gọn.
3. **Playful brand** — màu nổi, hình khối mềm, typography giàu cá tính và nhịp bố cục linh hoạt.

Không hỏi lại thông tin người dùng đã cung cấp rõ. Nếu brief đã đủ và người dùng đã yêu cầu làm ngay, tóm tắt hướng thiết kế rồi triển khai.

## Chốt hướng thiết kế

Trước khi dựng nhiều trang, mô tả ngắn thiết kế dự kiến:

- concept một câu;
- bảng màu và cặp font;
- key visual hoặc ngôn ngữ hình ảnh;
- hệ lưới, khoảng cách và nhịp trang;
- skeleton nội dung theo từng trang.

Với yêu cầu mơ hồ hoặc deck dài, xin xác nhận concept và skeleton trước. Có thể dựng một trang đại diện/style frame trước rồi mới nhân hệ thống sang phần còn lại.

## Chuẩn UI hoàn thiện

Một thiết kế hoàn thiện phải trông như sản phẩm đã được art-direct, không phải template mới điền chữ:

- Có một tiêu điểm thị giác rõ trên mỗi trang.
- Hệ phân cấp đọc được ngay: tiêu đề, thông tin chính, bằng chứng và chi tiết phụ.
- Căn lề, baseline, khoảng cách và kích thước lặp lại nhất quán.
- Màu, font, bo góc, nét và phong cách ảnh thuộc cùng một hệ thống.
- Key visual đủ mạnh; không dùng icon nhỏ hoặc các hộp rời rạc để thay cho hình ảnh chủ đạo.
- Mật độ cân bằng: không nhồi chữ, không để khoảng trống vô chủ đích.
- Các trang liền nhau có nhịp và silhouette khác nhau nhưng vẫn cùng một ngôn ngữ.
- Không biến mọi trang thành dashboard hoặc lưới card. Luân phiên có chủ đích giữa hero, split layout, editorial, timeline, quote, comparison, data và full-bleed visual.

Ưu tiên kích thước chữ tối thiểu:

- tiêu đề deck: `50 pt`;
- tiêu đề trang: `35 pt`;
- tiêu đề phụ: `24 pt`;
- nội dung: `16 pt`.

Chỉ giảm khi thật sự cần và vẫn đọc tốt trên điện thoại. Tránh tiêu đề hai dòng nếu có thể. Dùng font phổ biến hoặc font người dùng xác nhận có trên Canva.

## Khả năng chỉnh sửa trong Canva

Thiết kế theo nguyên tắc Canva-safe:

- text phải là text native;
- khối UI cơ bản dùng shape native;
- ảnh được nhúng và crop đúng tỷ lệ;
- bảng và chart giữ đơn giản;
- không rasterize cả trang chỉ để giữ vẻ ngoài;
- hạn chế font hiếm, merge phức tạp, hiệu ứng 3D, shadow/transparency quá đặc thù và OOXML tùy biến.

Canva có thể thay font, thay cách xuống dòng hoặc bỏ animation/transition khi import PPTX. Nếu người dùng cần chuyển động, mô tả thêm motion plan theo từng trang để họ áp dụng trong Canva; không hứa animation PowerPoint sẽ được giữ nguyên.

## Quy trình thực hiện

1. Hỏi và chốt ý tưởng, mục tiêu, phong cách.
2. Tạo design brief cùng skeleton trang.
3. Gọi `skill(name="powerpoint")` trước khi viết mã hoặc chỉnh PPTX.
4. Dùng hướng dẫn trong skill `powerpoint` để triển khai bằng `python-pptx`; không sao chép hoặc tự tạo một runtime PPTX khác.
5. Dựng style frame hoặc trang đại diện, sau đó tái sử dụng design tokens: màu, font, lề, spacing, shape và image treatment.
6. Dựng từng trang theo skeleton; trang mới kế thừa hệ thống thị giác của trang trước nhưng không lặp nguyên bố cục.
7. Render hoặc preview từng trang khi môi trường cho phép; kiểm tra riêng từng slide ở kích thước nhỏ.
8. Sửa mọi lỗi tràn, chồng, cắt chữ, crop ảnh, tương phản, căn lề và nhịp khoảng cách.
9. Lưu file rồi mở lại bằng `Presentation(output_path)` để xác nhận cấu trúc PPTX đọc được.

## Checklist trước khi giao

- Đúng số trang, thứ tự và tỷ lệ khung hình.
- Không còn placeholder hoặc nội dung mẫu ngoài chủ ý.
- Không có text overflow, overlap hoặc phần tử nằm ngoài slide.
- Typography, màu, lề và khoảng cách nhất quán.
- Ảnh đủ nét, crop hợp lý, không méo.
- Nội dung có tương phản và đọc được trên màn hình nhỏ.
- Các phần tử chính vẫn chỉnh sửa được sau khi import.
- File đã save và reopen thành công bằng `python-pptx`.
- Nêu rõ giới hạn chưa thể xác minh trực tiếp trong Canva hoặc PowerPoint thật.

Khi giao file, tóm tắt concept, tỷ lệ, số trang, mức độ editable và hướng dẫn ngắn: tải `.pptx` lên Canva bằng **Import file** rồi rà lại font, xuống dòng và animation.
