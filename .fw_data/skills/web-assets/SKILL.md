---
name: web-assets
description: Tìm, đánh giá và tích hợp ảnh, icon, font hoặc CDN cho website bằng các tool websearch/webfetch sẵn có. Dùng khi làm CodeWeb, landing page, portfolio, dashboard hoặc giao diện cần hình ảnh/asset trực tuyến. Chỉ tìm tài nguyên có sẵn; không tạo ảnh, không giả vờ có image-generation và không dùng URL chưa xác minh.
---

# Web assets chỉ tìm kiếm

Chọn hình ảnh vì nó giúp giao diện truyền đạt nội dung tốt hơn, không phải chỉ để lấp khoảng trống. Không gọi hoặc đề xuất công cụ tạo ảnh. Chỉ dùng asset có sẵn trong project hoặc tìm được trên web.

## Hiểu giới hạn của CLI

`websearch` hiện trả kết quả web dạng title, URL và snippet; nó không phải trình duyệt ảnh có thumbnail. Dùng nó để tìm **trang nguồn**, sau đó dùng `webfetch` kiểm tra trang, metadata, giấy phép và URL trực tiếp.

Không tuyên bố đã nhìn thấy hoặc xác minh chất lượng ảnh nếu tool chỉ trả văn bản. Nếu không thể xác minh ảnh trực tiếp, nói rõ giới hạn và chọn phương án an toàn.

## Quy trình

1. Xác định vai trò asset: hero, ảnh nội dung, background, avatar, logo, icon, texture hay font.
2. Nếu phong cách chưa rõ và ảnh ảnh hưởng lớn đến thiết kế, hỏi một câu ngắn về chủ đề, cảm xúc hoặc màu sắc. Không hỏi lại brief đã có.
3. Kiểm tra asset local trước bằng `glob`; tái sử dụng asset phù hợp thay vì tìm mới.
4. Tìm tối đa 2-3 truy vấn tập trung, ưu tiên tiếng Anh và thêm nguồn khi cần, ví dụ `site:unsplash.com`, `site:pexels.com` hoặc `site:commons.wikimedia.org`.
5. Mở 2-4 trang ứng viên tốt nhất bằng `webfetch`. Xác minh tác giả/nguồn, quyền sử dụng, chủ thể, tỷ lệ ảnh và URL trực tiếp nếu trang cung cấp.
6. Chọn ít asset nhưng đúng vai trò. Một hero mạnh tốt hơn nhiều ảnh nhỏ không liên quan.
7. Tích hợp vào layout hiện có, preview và kiểm tra tải lỗi, crop, tương phản, kích thước và responsive.

Nếu kết quả đầu yếu, tinh chỉnh truy vấn đúng một lần theo chủ thể, góc máy, màu hoặc tỷ lệ. Không dùng ảnh lệch nội dung chỉ để hoàn thành nhanh.

## Chọn nguồn

| Nhu cầu | Nguồn ưu tiên | Quy tắc |
| --- | --- | --- |
| Ảnh chụp thương mại/phổ thông | Unsplash, Pexels | Mở trang ảnh gốc và kiểm tra điều kiện sử dụng trước khi nhúng. |
| Ảnh lịch sử, địa điểm, nhân vật, khoa học | Wikimedia Commons, Openverse | Kiểm tra giấy phép của từng file và ghi attribution khi bắt buộc. |
| Logo hoặc hình sản phẩm | Website chính thức, press kit, brand kit | Không lấy từ trang re-upload không rõ nguồn; giữ đúng tỷ lệ và màu thương hiệu. |
| Icon giao diện | Bộ icon project đang dùng; nếu chưa có thì Lucide, Heroicons hoặc Font Awesome | Chỉ dùng một hệ icon nhất quán; ưu tiên SVG/icon package hơn ảnh raster. |
| Font web | Font local/system trước; Google Fonts hoặc nguồn chính thức khi thực sự cần | Không thêm font ngoài nếu làm chậm web mà khác biệt thị giác không đáng kể. |

Các hostname thường gặp như `images.unsplash.com`, `images.pexels.com`, `upload.wikimedia.org`, `cdn.jsdelivr.net`, `cdnjs.cloudflare.com` và `unpkg.com` chỉ là **ứng viên**. Luôn xác minh URL thật bằng nguồn chính thức; không tự bịa đường dẫn từ mẫu hostname.

## Quy tắc URL và CDN

- Chỉ dùng URL HTTPS trực tiếp, ổn định và trả đúng loại asset.
- Không dùng URL trang tìm kiếm làm `src` ảnh.
- Không dùng signed URL, URL có token hết hạn, blob URL, endpoint random hoặc URL đổi ảnh mỗi lần tải.
- Không hotlink nếu nguồn không cho phép hoặc điều kiện sử dụng không rõ.
- Với thư viện JS/CSS, ưu tiên dependency sẵn có trong project. Nếu buộc dùng CDN, pin phiên bản cụ thể; không dùng `latest`.
- Không tải cùng thư viện từ nhiều CDN và không thêm framework chỉ để có một icon hoặc một ảnh.
- Giữ URL nguồn/trang giấy phép trong comment gần asset hoặc ghi chú ngắn nếu attribution là bắt buộc.

## Tích hợp vào UI

- Khai báo `width`, `height` hoặc `aspect-ratio` để tránh layout nhảy khi ảnh tải.
- Dùng `object-fit: cover` cho ảnh crop; không kéo méo ảnh.
- Hero tải ưu tiên; ảnh dưới màn hình dùng `loading="lazy"` và `decoding="async"`.
- Viết `alt` mô tả mục đích/nội dung. Với ảnh trang trí thuần túy, dùng `alt=""`.
- Background có chữ phải có overlay đủ tương phản và vẫn đọc được khi ảnh không tải.
- Chuẩn bị màu nền hoặc gradient fallback; lỗi CDN không được làm vỡ bố cục.
- Chọn độ phân giải gần kích thước hiển thị. Không tải ảnh 4K cho thumbnail nhỏ.
- Trên mobile, kiểm tra điểm crop quan trọng không bị cắt mất khuôn mặt, sản phẩm hoặc chữ trong ảnh.

Không rasterize text, nút hoặc icon UI thành ảnh nếu HTML/CSS/SVG làm được. Ảnh chỉ đảm nhiệm phần thị giác thật sự cần ảnh.

## Báo cáo khi hoàn thành

Tóm tắt ngắn:

- asset nào được dùng và nằm ở đâu;
- nguồn/trang giấy phép nếu cần attribution;
- asset nào vẫn là URL ngoài;
- giới hạn chưa xác minh được như hotlink, chất lượng thật hoặc khả năng truy cập ngoại tuyến.

Nếu không tìm được asset đủ tin cậy, giữ layout bằng typography, màu và shape CSS rồi báo người dùng; không thay bằng ảnh giả hoặc ảnh không rõ nguồn.
