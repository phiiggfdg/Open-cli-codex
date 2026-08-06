---
name: web-assets
description: Tìm, đánh giá và tích hợp ảnh, icon, font hoặc CDN cho website bằng các tool websearch/webfetch sẵn có. Dùng khi làm CodeWeb, landing page, portfolio, dashboard hoặc giao diện cần hình ảnh và asset trực tuyến. Chỉ tìm tài nguyên có sẵn; không tạo ảnh, không giả vờ có image-generation và không dùng URL chưa xác minh.
---

# Web assets chỉ tìm kiếm

Chọn asset vì nó giúp giao diện truyền đạt nội dung tốt hơn, không phải chỉ để lấp khoảng trống.

Chỉ sử dụng:

- asset đã có trong project;
- asset tìm được từ nguồn đáng tin cậy;
- URL đã được xác minh;
- tài nguyên có điều kiện sử dụng phù hợp.

Không:

- gọi hoặc đề xuất công cụ tạo ảnh;
- tuyên bố có khả năng image generation;
- tự bịa URL;
- suy đoán đường dẫn từ hostname hoặc tên file;
- dùng asset không rõ nguồn chỉ để hoàn thành nhanh;
- thêm framework hoặc dependency lớn chỉ để lấy một icon, font hoặc ảnh.

Ưu tiên:

1. Đúng nội dung và vai trò thị giác.
2. Nguồn đáng tin cậy.
3. Điều kiện sử dụng rõ ràng.
4. Độ ổn định.
5. Hiệu năng.
6. Khả năng truy cập.
7. Quyền riêng tư.
8. Minimum asset và minimum dependency giải quyết đúng yêu cầu.

---

## Hiểu giới hạn của CLI

`websearch` trả kết quả web dạng:

- title;
- URL;
- snippet;
- metadata văn bản nếu có.

Nó không phải trình duyệt ảnh có thumbnail đầy đủ.

Dùng `websearch` để tìm:

- trang nguồn;
- trang sản phẩm;
- press kit;
- brand kit;
- trang file;
- trang giấy phép;
- tài liệu CDN;
- tài liệu package.

Sau đó dùng `webfetch` để kiểm tra:

- nguồn;
- tác giả;
- mô tả asset;
- điều kiện sử dụng;
- attribution;
- metadata;
- URL trực tiếp nếu trang cung cấp;
- kích thước hoặc tỷ lệ khi có metadata đáng tin cậy;
- hướng dẫn nhúng hoặc tải xuống.

Không tuyên bố đã nhìn thấy hoặc đánh giá trực tiếp:

- bố cục ảnh;
- ánh sáng;
- màu sắc;
- độ nét;
- khuôn mặt;
- góc máy;
- crop;
- chất lượng thẩm mỹ;

nếu tool chỉ trả văn bản.

Không suy đoán tỷ lệ, độ phân giải hoặc chất lượng chỉ từ title và snippet.

Nếu không thể kiểm tra hình ảnh trực tiếp:

- nói rõ giới hạn;
- dựa trên metadata và mô tả nguồn;
- chọn phương án an toàn;
- không mô tả chi tiết thị giác chưa được xác minh.

---

## Hiểu brief asset

Trước khi tìm kiếm, xác định:

- loại website;
- mục tiêu giao diện;
- người xem;
- phong cách;
- màu sắc;
- chủ đề;
- asset đã có;
- framework hoặc stack hiện tại;
- asset cần local hay remote;
- yêu cầu offline;
- yêu cầu về quyền riêng tư;
- yêu cầu attribution;
- giới hạn hiệu năng.

Xác định vai trò cụ thể của từng asset:

- hero image;
- ảnh nội dung;
- background;
- avatar;
- logo;
- product image;
- illustration;
- texture;
- icon;
- favicon;
- font;
- CSS library;
- JavaScript library;
- CDN dependency.

Nếu phong cách chưa rõ và asset ảnh hưởng lớn đến thiết kế, hỏi một câu ngắn về:

- chủ đề;
- cảm xúc;
- màu;
- loại hình ảnh;
- thương hiệu;
- mức độ tối giản hoặc nổi bật.

Không hỏi lại brief người dùng đã cung cấp rõ.

Nếu brief đã đủ, không dừng để hỏi thêm chỉ vì hình thức.

---

## Kiểm tra asset trong project trước

Trước khi tìm web:

1. Dùng `glob` để tìm asset local.
2. Kiểm tra thư mục thường gặp:
   - `assets`;
   - `images`;
   - `img`;
   - `icons`;
   - `fonts`;
   - `public`;
   - `static`;
   - `src/assets`.
3. Kiểm tra package icon hoặc font đã được cài.
4. Tái sử dụng asset phù hợp thay vì tải thêm.
5. Không tạo bản sao của cùng một asset nếu không cần.

Ưu tiên asset đã có khi:

- đúng nội dung;
- đủ chất lượng;
- phù hợp hệ thống hình ảnh;
- đã được project sử dụng;
- tránh thêm dependency hoặc request ngoài.

Không dùng asset local chỉ vì nó tồn tại nếu nó lệch chủ đề hoặc làm giảm chất lượng giao diện.

---

## Quy trình tìm kiếm

1. Xác định vai trò asset.
2. Kiểm tra asset local.
3. Xác định loại nguồn phù hợp.
4. Bắt đầu với tối đa 2 đến 3 truy vấn tập trung.
5. Ưu tiên truy vấn tiếng Anh khi nguồn quốc tế tốt hơn.
6. Thêm domain hoặc loại nguồn khi cần.
7. Mở 2 đến 4 trang ứng viên tốt nhất bằng `webfetch`.
8. Xác minh nguồn, điều kiện sử dụng và URL.
9. Chọn ít asset nhưng đúng vai trò.
10. Tích hợp vào layout.
11. Preview và kiểm tra.
12. Báo rõ giới hạn chưa xác minh.

Ví dụ truy vấn:

```text
minimal fintech dashboard hero illustration official source
```

```text
site:unsplash.com sustainable architecture office exterior
```

```text
site:pexels.com vietnamese student studying laptop
```

```text
site:commons.wikimedia.org Ho Chi Minh City skyline
```

```text
official brand press kit company name logo svg
```

```text
official lucide icons npm documentation
```

Chỉ mở rộng tìm kiếm khi:

- kết quả đầu không đủ;
- nguồn không rõ giấy phép;
- URL không ổn định;
- task cần nhiều nhóm asset khác nhau;
- asset hiện tại không phù hợp tỷ lệ hoặc chủ thể.

Nếu kết quả đầu yếu, tinh chỉnh truy vấn đúng một lần theo:

- chủ thể;
- góc máy;
- màu;
- bối cảnh;
- tỷ lệ;
- phong cách;
- loại nguồn.

Không tìm kiếm lan man khi đã có asset phù hợp.

Không dùng ảnh lệch nội dung chỉ để kết thúc nhanh.

---

## Chọn ít