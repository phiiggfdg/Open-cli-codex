---
name: dependency-management
description: Quản lý thư viện, audit dependency và quy trình cài đặt package an toàn. Dùng khi cần thêm import mới, cài package qua pip/npm/yarn, hoặc kiểm tra tính tương thích thư viện trong dự án.
---

# Dependency Management — Quản lý & Cài đặt Thư viện

Ngăn chặn việc cài đặt bừa bãi các package không cần thiết, bảo vệ tính ổn định và bảo mật của dự án.

## 1. Quy tắc "Ưu tiên giải pháp không thêm Dependency" (No-New-Dependency)

Trước khi quyết định thêm bất kỳ thư viện bên ngoài nào:
1. **Kiểm tra thư viện có sẵn**:
   - Dùng `grep` kiểm tra file cấu hình dự án (`requirements.txt`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`...) để xem thư viện đó hoặc thư viện tương đương đã được cài chưa.
2. **Tận dụng Thư viện chuẩn (Standard Library)**:
   - Nếu công việc có thể giải quyết tốt bằng thư viện chuẩn (ví dụ `json`, `sqlite3`, `urllib`, `re`, `pathlib`, `dataclasses`, `http.client`...) trong 20–50 dòng code ➔ **Ưu tiên tự viết, không cài thêm package**.
3. **Đánh giá rủi ro**:
   - Cài thêm dependency làm tăng dung lượng, rủi ro bảo mật supply-chain và tăng thời gian build/CI.

## 2. Quy trình xin phép bắt buộc qua `question`

Nếu package mới là **thực sự bắt buộc**:
- **KHÔNG ĐƯỢC TỰ Ý CHẠY LỆNH CÀI ĐẶT**.
- Phải dùng tool `question` để trình bày với người dùng:
  1. Tên package cần cài.
  2. Lý do cụ thể vì sao thư viện chuẩn hoặc các package hiện có không đáp ứng được.
  3. File manifest/lockfile nào sẽ bị thay đổi (`package.json`, `requirements.txt`).
- Chỉ chạy lệnh cài đặt **sau khi người dùng đã xác nhận đồng ý**.

## 3. Quy chuẩn lệnh cài đặt

- **Môi trường Termux / Android**:
  - `pip install <package> --break-system-packages` (bắt buộc phải có cờ `--break-system-packages`, thiếu sẽ bị policy chặn).
- **Node.js**:
  - Dùng đúng package manager mà dự án đang dùng (`npm`, `pnpm`, hoặc `yarn`).
- **Ghi nhận vào Manifest**:
  - Luôn cập nhật tên và version vào `requirements.txt` hoặc `package.json` để người khác clone repo có thể cài lại được.
