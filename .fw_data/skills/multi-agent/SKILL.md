---
name: multi-agent
description: Chiến lược điều phối, phân chia task và ủy quyền cho subagent hiệu quả. Dùng khi cân nhắc có nên gọi subagent hay không, phân định phạm vi subtask độc lập và tránh trùng lặp công việc gây lãng phí tài nguyên.
---

# Multi-Agent Orchestration — Điều phối & Quản lý Subagent

Quản lý subagent thông minh, tiết kiệm quota token và tránh xung đột thao tác trên codebase.

## 1. Khi nào KHÔNG ĐƯỢC gọi Subagent (Chống lãng phí)

**TUYỆT ĐỐI KHÔNG gọi subagent trong các trường hợp sau:**
- Sửa lỗi đơn giản chỉ trong 1 file.
- Các bug fix trực tiếp, rõ ràng đã biết nguyên nhân.
- Nhiệm vụ mà Main Agent đã đọc và hiểu rõ toàn bộ ngữ cảnh.
- Khi các bước phụ thuộc tuần tự chặt chẽ vào nhau (Main Agent tự làm sẽ nhanh và ít tốn token hơn nhiều).

## 2. Khi nào NÊN gọi Subagent

Chỉ gọi subagent khi công việc đáp ứng đủ 3 tiêu chí:
1. **Tính độc lập cao**: Subtask hoàn toàn độc lập, không phụ thuộc vào trạng thái đang sửa của Main Agent.
2. **Khối lượng tra cứu lớn / Chuyên biệt**: Khảo sát tài liệu rộng, nghiên cứu giải pháp độc lập, hoặc thực hiện một tác vụ song song tách biệt.
3. **Phạm vi rõ ràng**: Có mô tả đầu vào và định dạng đầu ra (output format) cụ thể.

## 3. Quy tắc ủy quyền & An toàn

1. **Ưu tiên Subagent Read-only (Nghiên cứu / Phân tích)**:
   - Giao cho subagent nhiệm vụ đọc hiểu, so sánh, phân tích tài liệu và tổng hợp kết quả.
   - Hạn chế cấp quyền ghi/sửa file cho subagent nếu không thật sự cần thiết.
2. **Chống trùng lặp công việc (No Duplicate Work)**:
   - Trước khi gọi subagent, xác định rõ subtask này Main Agent sẽ KHÔNG làm lại.
   - Không giao cho subagent các file mà Main Agent đang chuẩn bị sửa.
3. **Main Agent nắm quyền tích hợp cuối cùng (Single Integration Owner)**:
   - Subagent chỉ trả về kết quả nghiên cứu / đề xuất / dữ liệu.
   - **Main Agent chịu trách nhiệm tổng hợp, quyết định áp dụng vào codebase và thực hiện chỉnh sửa file cuối cùng**.
