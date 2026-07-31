## Simplicity First (ưu tiên cao nhất)

**Minimum code giải quyết đúng vấn đề. Không thêm gì ngoài yêu cầu.**

- không retry cùng 1 lệnh khi dính lỗi hoạc bị police chặn
- Không thêm feature ngoài những gì được hỏi.
- Không tạo abstraction cho code chỉ dùng 1 lần.
- Không thêm "flexibility" hay "configurability" không ai xin.
- Không xử lý error cho tình huống không thể xảy ra.
- Nếu viết 200 dòng mà có thể là 50 dòng → viết lại.

Tự hỏi: "Senior engineer có nói cái này overcomplicated không?" Nếu có → đơn giản hóa.

## Quy tắc chỉnh sửa

- Sửa đúng file theo module map, không đặt logic sai layer.
- Biến global dùng chung → khai báo ở module phù hợp nhất, không tạo bản sao.
- Thêm feature ảnh hưởng nhiều module hoặc phần nhạy cảm (auth, payment, migration, config production, CI/CD) → hỏi trước.
- Task lớn, nhiều module hoặc phạm vi chưa rõ → gọi `skill(name="spec-driven")` trước khi lập kế hoạch và sửa code.
- Khi làm việc với PowerPoint (`.pptx`) → gọi `skill(name="powerpoint")` trước khi tạo hoặc chỉnh sửa file.
- Khi người dùng yêu cầu Canva, thiết kế slide/UI để import vào Canva hoặc PPTX thiên về visual → gọi `skill(name="canva")` trước. Skill này sẽ yêu cầu hỏi ý tưởng, chốt hướng thẩm mỹ rồi gọi tiếp `powerpoint` để tạo PPTX.
- Khi làm website cần tìm ảnh, icon, font hoặc CDN → gọi `skill(name="web-assets")` trước. Skill này chỉ tìm và xác minh tài nguyên có sẵn bằng `websearch`/`webfetch`, không tạo ảnh và không bịa URL.

## Môi trường: Termux / Android

- `pip install` luôn dùng `--break-system-packages`.
- Không có `sudo`, không dùng `apt`, `systemctl` hoặc lệnh cần quyền root.

## Bash tool: lệnh được phép

- Mỗi tool call chỉ chạy **một command**. Không dùng `;`, `&&`, `||`, pipe,
  redirect, subshell, biến shell, command substitution hoặc lệnh nhiều dòng.
- Inspect/status: `pwd`, `ls` (không recursive), `rg`, `grep`, `wc`, `file`, `stat`,
  `tree`, `which`, `basename`, `dirname`, `date`, `uname`, `whoami`, `echo`, `printf`.
- Dev/build: `git`, `pytest`, `python`/`python3`, `node`, `npm`, `pnpm`, `yarn`,
  `make`, `pip`/`pip3`, `ruff`, `mypy`, `eslint`, `tsc`.
- `python -c`, `node -e/-p`, shell `bash/sh/zsh`, executable qua path, path ngoài
  project và mọi command không có trong danh sách đều bị chặn.
- `git push`, `git clean`, `git reset --hard`, package publish và `ls -R` bị chặn cứng.
- File mutation dùng `write`/`edit`/`delete`/`apply_patch`; không dùng `rm`, `cp`,
  `mv`, `mkdir`, `touch`, `sed -i`. File inspection ưu tiên `read`/`glob`/`grep`.
- Python/Node script là code execution: chỉ chạy file tin cậy trong project.
- Server nền chỉ dùng `serve:` với `python -m http.server`, `node <file>`,
  `npm run/start`, hoặc `pnpm`/`yarn` `run|start|dev|serve|preview`.

## Section markers & Output

- File mới >80 dòng dùng `##== NAME ==##`.
- Không emoji trong output.
- Sau khi hoàn thành: tóm tắt ngắn gọn các file đã thay đổi và cách chạy/verify.
