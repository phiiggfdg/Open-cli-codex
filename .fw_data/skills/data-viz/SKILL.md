---
name: data-viz
description: Đọc dữ liệu (CSV/JSON/log/DB) → tính toán đúng → chọn chart/bảng phù hợp. Dùng khi user yêu cầu phân tích số liệu, vẽ biểu đồ, tổng hợp báo cáo từ data, hoặc bất kỳ việc gì đi từ dữ liệu thô tới kết luận/visualization. Không khóa công nghệ cụ thể — áp dụng cho pandas, SQL thuần, JS/Chart.js, hay bất kỳ stack nào user đang dùng.
---

# Data analysis & visualization

Lỗi phổ biến nhất ở việc này không phải code sai cú pháp — mà là **kết luận
sai dù code chạy được**: số liệu bịa khi thiếu data, chart méo do outlier
không xử lý, hoặc chọn loại chart sai khiến người xem hiểu lầm. Skill này
tập trung ngăn 3 lỗi đó, không dạy cú pháp thư viện cụ thể.

## 1. Đọc data trước khi tính — không đoán schema

- Luôn xem raw data thật (vài dòng đầu, dtype/kiểu từng cột, số dòng) trước
  khi viết bất kỳ phép tính nào. Không giả định tên cột, định dạng ngày
  tháng, đơn vị, hay encoding chỉ từ tên file hay từ trí nhớ về "định dạng
  thường gặp".
- Kiểm tra missing value / null / dòng trống ngay từ đầu — biết rõ đang có
  bao nhiêu dòng thiếu dữ liệu ở cột nào trước khi tính toán trên nó.
- Nếu schema không rõ hoặc dữ liệu không đúng như user mô tả (thiếu cột, số
  dòng bất thường, kiểu dữ liệu lệch), báo ngay và hỏi thay vì tự suy diễn
  để tính tiếp cho "xong việc".

## 2. Tính toán — không bịa số khi thiếu dữ liệu

- Không tự điền giá trị giả định vào chỗ trống trong bảng/báo cáo cuối cùng.
  Nếu một phép tính không thể thực hiện được vì thiếu data, nói rõ thiếu gì
  — không suy ra "ước tính hợp lý" rồi trình bày như số liệu thật.
- Với mọi con số tổng hợp (trung bình, tổng, %, tỉ lệ tăng trưởng...), nêu
  rõ nó được tính từ cột/điều kiện lọc nào — tránh tình trạng con số đúng
  về mặt code nhưng trả lời sai câu hỏi (ví dụ tính trung bình trên toàn bộ
  dữ liệu trong khi user hỏi trung bình theo từng nhóm).
- Kiểm tra outlier trước khi báo cáo số tổng hợp nhạy cảm với outlier
  (trung bình, tổng). Không tự động loại bỏ outlier mà không nói — quyết
  định loại bỏ hay giữ lại phải tường minh và có lý do, không âm thầm lọc.
- Với time series: kiểm tra khoảng trống thời gian (gap), trùng lặp
  timestamp, và có đang so sánh đúng kỳ (apple-to-apple: cùng số ngày,
  cùng mùa vụ) trước khi kết luận xu hướng.
- Verify công thức bằng cách tính tay 1-2 điểm dữ liệu nhỏ khi kết quả nhìn
  bất thường (số quá tròn, quá lớn/nhỏ so với kỳ vọng) trước khi báo cáo,
  thay vì tin ngay kết quả code chạy ra.

## 3. Chọn loại chart theo câu hỏi, không theo thói quen

Chọn chart theo câu trả lời cần truyền đạt, không phải theo loại chart hay
dùng:

- **So sánh giữa các nhóm** (ít nhóm, một thời điểm) → bar chart.
- **Xu hướng theo thời gian** → line chart. Nhiều series → giới hạn số
  đường để tránh rối mắt, cân nhắc small multiples nếu quá nhiều nhóm.
- **Phân bố một biến** → histogram hoặc box plot (box plot tốt hơn khi cần
  so sánh phân bố giữa nhiều nhóm cùng lúc, đồng thời lộ rõ outlier).
- **Quan hệ giữa 2 biến số** → scatter plot.
- **Tỉ lệ phần của tổng thể** → pie/donut chỉ khi số nhóm ít (≤5-6) và tổng
  có ý nghĩa 100%; nhiều nhóm hơn thì bar chart đọc dễ hơn nhiều.
- **Phân bố địa lý** → map, không ép vào bar/pie chỉ vì tiện thư viện.

Tránh các lỗi trực quan hóa gây hiểu lầm:

- Trục Y không bắt đầu từ 0 ở bar chart → phóng đại sai lệch giữa các cột.
  Nếu cần zoom trục để thấy khác biệt nhỏ, nói rõ trục đã cắt, hoặc dùng
  line/dot chart thay vì bar.
- Quá nhiều màu/nhóm trên 1 chart khiến không đọc được — cân nhắc gộp nhóm
  nhỏ vào "khác" hoặc tách thành nhiều chart.
- Chart 3D, pie chart quá nhiều lát, hoặc dual-axis dễ đọc sai — chỉ dùng
  khi thực sự cần và giải thích rõ cách đọc.
- Luôn có title, trục ghi rõ đơn vị, và chú thích (legend) nếu có nhiều
  series — chart thiếu ngữ cảnh dễ bị hiểu sai dù số liệu đúng.

## 4. Trình bày kết quả

- Dẫn số liệu cụ thể trong câu trả lời, không chỉ mô tả chung chung ("có xu
  hướng tăng") — nói tăng bao nhiêu, từ đâu tới đâu, trong khoảng thời gian
  nào.
- Nếu kết luận dựa trên tập dữ liệu nhỏ hoặc có nhiều giá trị thiếu, nói rõ
  giới hạn đó thay vì trình bày như một kết luận chắc chắn.
- Khi build bảng/chart thành file hoặc UI, đặt trong ngữ cảnh: nguồn dữ liệu
  là gì, khoảng thời gian nào, lọc theo điều kiện gì — để người đọc sau này
  (kể cả chính user) không hiểu nhầm phạm vi.

## Công nghệ

Không khóa vào 1 stack cụ thể. Áp dụng đúng công nghệ user đang có sẵn
trong project (pandas, SQL thuần, numpy, JS + Chart.js/Recharts/D3, Excel
formula...) — nguyên tắc ở trên là về cách đọc/tính/chọn chart, không phải
về cú pháp thư viện nào.
