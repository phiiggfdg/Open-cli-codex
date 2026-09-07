---
name: multi-agent
description: Quy tắc AN TOÀN & phối hợp sau khi đã quyết định gọi subagent (task hoặc delegate) — không phải tiêu chí có nên gọi hay không (tiêu chí đó nằm trong description của từng tool). Dùng khi đang soạn 1 lệnh gọi subagent để tránh trùng lặp công việc hoặc xung đột thao tác trên codebase.
---

# Multi-Agent Orchestration — Sau khi đã quyết định gọi Subagent

Quyết định "có nên gọi subagent hay không" đã nằm sẵn trong `description` của
tool `task` và tool `delegate` — model đọc field đó ngay khi cân nhắc tool
call, đúng thời điểm cần thông tin đó nhất. Skill này KHÔNG lặp lại tiêu chí
đó (tránh 2 nguồn chân lý dễ lệch nhau theo thời gian). Skill này chỉ có giá
trị SAU khi đã quyết định gọi — về cách giao việc an toàn, không trùng lặp.

## 1. Quy tắc ủy quyền & An toàn

1. **Ưu tiên Subagent Read-only (Nghiên cứu / Phân tích)**:
   - Giao cho subagent nhiệm vụ đọc hiểu, so sánh, phân tích tài liệu và tổng hợp kết quả.
   - Chỉ giao nhiệm vụ sửa file khi thật sự cần. Tham số `tools` của `task` và
     `delegate` chỉ **bổ sung** tool vào bộ mặc định, không thể thu hẹp quyền;
     vì vậy phải giới hạn phạm vi bằng mô tả, `target_files` và `expected_output`.
2. **Chống trùng lặp công việc (No Duplicate Work)**:
   - Trước khi gọi subagent, xác định rõ subtask này Main Agent sẽ KHÔNG làm lại.
   - Không giao cho subagent các file mà Main Agent đang chuẩn bị sửa.
   - Với `delegate`: đặt `target_files`/`target_location` đúng và cụ thể — đây
     cũng là key dùng để dedup, nếu gọi lại gần giống với cùng target, bản cũ
     sẽ tự động bị nén sớm trong lịch sử.
3. **Main Agent nắm quyền tích hợp cuối cùng (Single Integration Owner)**:
   - Subagent chỉ trả về kết quả nghiên cứu / đề xuất / dữ liệu theo đúng
     `expected_output` đã yêu cầu (với `delegate`) hoặc mô tả đã giao (với `task`).
   - **Main Agent chịu trách nhiệm tổng hợp, quyết định áp dụng vào codebase và
     thực hiện chỉnh sửa file cuối cùng** — trừ khi chính `expected_output`
     yêu cầu subagent tự sửa file.

## 2. `task` vs `delegate` — chọn cái nào

- **`task`**: subagent dùng CHUNG model với agent chính, hội thoại nội bộ dài,
  phù hợp khi cần khám phá/steer nhiều bước, chưa biết rõ hết phạm vi trước.
- **`delegate`**: subagent dùng model/provider RIÊNG (chọn qua
  `/delegate-model`), system prompt tối giản không kế thừa gì từ agent chính,
  bắt buộc phân loại `task_type` + nêu rõ `expected_output` trước khi giao.
  Phù hợp khi việc đã đủ rõ để giao trọn gói 1 lần, không cần steer giữa
  chừng — ưu tiên `delegate` trong trường hợp này vì output ngắn gọn, có
  khuôn cố định, ít làm bẩn context agent chính hơn.
