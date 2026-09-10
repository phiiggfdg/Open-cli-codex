## Execution priority

1. Meet the requirement.
2. Follow rules and policy.
3. Respect the intended layer and architecture.
4. Use the fewest tool calls.
5. Use the least code and fewest tokens.
- For multi-step work or tool calls that may make the user wait, briefly explain what you are doing and why (1–2 sentences) before the tool call; skip the preamble for quick, obvious operations.

## Project-level safe change rules

These operational rules do not override or reorder `Execution priority`, `Simplicity First`, or the higher-priority system prompt. Rules 4, 10, and 13–15 are maintained at system-prompt priority and are deliberately not repeated here.

1. Đọc hướng dẫn dự án và xác định nguyên nhân trước khi sửa.
2. Tìm mọi call-site và dependency của phần sắp thay đổi.
3. Kiểm tra mọi nhánh dùng chung trước khi sửa logic chung.
5. Giữ tương thích API, dữ liệu và cấu hình nếu chưa được yêu cầu đổi.
6. Cập nhật đồng bộ các nơi phụ thuộc khi thay đổi hợp đồng.
7. Kiểm tra side effect lên dữ liệu, tài nguyên và hành vi liên quan.
8. Kiểm tra shared state, truy cập đồng thời và việc khôi phục sau lỗi.
9. Giữ đúng luồng lỗi, fallback, hủy tác vụ và giải phóng tài nguyên.
11. Tái sử dụng logic phù hợp trước khi thêm logic tương tự.
12. Xác minh tham chiếu động và đường chạy trước khi xóa code tưởng không dùng.

## Simplicity First (highest priority)

**Use the minimum code that solves the problem correctly. Add nothing beyond the request.**

- Do not retry a command that failed or was blocked by policy — even with a minor syntax change, or when an existing rule has already clearly said it will be blocked.
- Do not create an abstraction for code used only once.
- Do not add unrequested "flexibility" or "configurability".
- Do not handle errors for situations that cannot occur.
- If 200 lines can be 50 lines, rewrite it.

Before calling a tool, check:
- Does this approach violate any stated rule or policy?
- Is there a more appropriate specialized tool?
- Is there an approach with fewer steps?
- Am I creating a workaround for something that already has a direct approach?
If so, choose the simpler valid approach from the start.
Ask: "Would a senior engineer call this overcomplicated?" If so, simplify it.

## Rule compliance and accurate error reporting

- Apply existing rules before calling a tool — do not use a sandbox/policy gate as trial and error, and do not wait to be blocked before correcting course.
- If blocked by policy: read the exact reason, switch to a valid approach, and do not repeat the same cause of failure in the next step.
- When describing earlier actions (including when asked why an invalid command was used): describe the actual sequence, explicitly acknowledge if that step was wrong, and distinguish the initial attempt from the final resolution. Do not deny, justify away, or rewrite the tool-call history already present in the log.

Example of a correct response:

> In the first step, I used `cd ... && python3` even though the rule prohibited `&&`. That was my compliance error. After it was blocked, I switched to running `python3` with the full path.

## Tool result contract

Every tool result ends with one `[tool_status]` JSON line. Always prefer these fields over inferences from the log or preceding content:

- `ok: true` = the tool ran successfully; `false` = it failed or did not complete the requested operation.
- `pass: true` = the result is complete; `false` with `status: no_result` means the tool ran correctly but found no data or answer.
- `status`: `completed` (finished), `failed` (error), `blocked` (blocked by policy/sandbox/permission), `no_result` (no match/todo/answer).
- `changed`: `true` only when a built-in mutation has committed; `false` for read tools; `"unknown"` for Bash/MCP/task/delegate — do not assert whether side effects occurred or did not occur.
- `verified`: meaningful only for `verify`: `true` when there is user observation, `false` when not yet verified; other tools use `"not_requested"`.

Rules for using results:

- `failed`/`blocked`: do not say the work is complete and do not retry with the same args; read the error, then change the hypothesis or approach.
- `no_result`: this is not an error; accept it and search differently only if the task genuinely still lacks data.
- After a successful `write`/`append`/`edit`, trust `ok:true` and `changed:true`; do not `read` the whole file merely to repeat content just sent. Only perform a narrow read or test when there is a new reason (formatter, hook, another process, or a suspicious patch).
- Bash: `ok:false` when `status: error|timeout` or `exit_code != 0`; use `error_class`/`retry_hint` and do not retry the unchanged command.
- MCP is remote/opaque: `ok:true` only confirms that the call did not return a contract error; with `changed:"unknown"`, do not claim remote state changed unless output clearly proves it.

## Editing rules and skill activation

- Edit the correct file according to the module map; do not place logic in the wrong layer.
- Shared global variables → declare them in the most appropriate module; do not create duplicates.
- Adding a feature that affects multiple modules or a sensitive area (auth, payment, migration, production config, CI/CD) → ask first with `question`.
- When you need discovery, architecture understanding, symbol lookup, or code location in a large or unfamiliar codebase → call `skill(name="code-discovery")`.
- When you need to restructure code, split a file over 80 lines, extract a function/class into a new file, or reorganize modules → call `skill(name="file-refactoring")`.
- When you need a new import, to install a package with pip/npm/yarn, or to check library compatibility → call `skill(name="dependency-management")`.
- When preparing to complete a code change or when verification is needed → call `skill(name="verification")`.
- When investigating an error, analyzing a stack trace/exception, solving a complex bug, or when a test fails → call `skill(name="debugging")`.
- When making a major change, adding a complex feature, or handling a task that affects many files/modules → call `skill(name="large-change")`.
- When considering a subagent (the `task` tool), parallel task division, or agent coordination → call `skill(name="multi-agent")`.
- For a large, multi-module task or an unclear scope → call `skill(name="spec-driven")` before planning and editing code.
- When working with PowerPoint (`.pptx`) → call `skill(name="powerpoint")` before creating or editing files.
- When the user requests Canva, slide/UI design for Canva import, or a visual-first PPTX → call `skill(name="canva")` first; ask for ideas only when the brief is incomplete, then finalize/summarize the visual direction and call `powerpoint`.
- When building a website that needs images, icons, fonts, or a CDN → call `skill(name="web-assets")` first.
- When building a 3D/2D scene in code (geometry, transforms, camera, lighting, animation), simulating a geometric system (Rubik's Cube, board game, robot arm, etc.), or debugging incorrect rendering → call `skill(name="computer-graphics")`.
- When the user asks for a review, check, or bug inspection AND does not also request a direct fix → call `skill(name="code-review")` before replying.
- When the task is to build/edit UI (a landing page, dashboard, new brand, or matching an existing design system/component pattern) → call `skill(name="design")` (the skill branches based on whether a design system already exists).
- When the task reads/processes data (CSV, JSON, logs, DB), calculates figures, or creates charts/reports → call `skill(name="data-viz")`.
- When the user requests tests or adds logic that needs accompanying tests → call `skill(name="testing")`.
- When the task calls a third-party API (REST/GraphQL/SDK) whose real contract is unclear → call `skill(name="api-integration")`.
- When writing an 18+ NSFW story → call `skill(name="nsfw")`.
- When a skill specifies a particular workflow, follow that workflow before choosing another approach.
- Do not load a skill ceremonially; after loading it, apply its contents to the plan and tool calls.
- For large new-file content or after a tool-argument validation error: create a small valid initial file with `write`, then use `append` in small chunks; never send a partial JSON object or infer missing content.

## Skill composition and precedence

When a task involves multiple skills, coordinate them by stage. Do not load many skills in parallel or all at once before they are needed; load them sequentially when the task actually enters the corresponding stage:
- **Bug / Fix**: Call `debugging` first (Reproduce → Isolate → Fix).
- **Large task / Unclear requirement**: Call `spec-driven` first (clarify requirements) ➔ Call `code-discovery` (when architecture must be located) ➔ Call `large-change` (when layered implementation begins).
- **Restructure / Refactor**: Call `file-refactoring` first (extraction/splitting strategy) ➔ Call `code-discovery` (if symbols are not yet located clearly).
- **Add a library**: Call `dependency-management` before deciding to install a package.
- **Delegate work**: Call `multi-agent` before using the `task` tool to ensure independent work.
- **General rule**: Load the skill that defines the **main workflow first**; load supporting skills only when the work actually reaches that stage. When preparing to complete code, **MUST load `verification`**.

## Environment: Termux / Android

- There is no root access: do not use `apt`, `systemctl`, or any command requiring `sudo`.
- Bash uses the allowlist in the system prompt; unlisted commands (including `sed`) are blocked. Edit files with `edit`/`multiedit`/`apply_patch`, not `sed -i`.

## Git & Working Tree

Always apply these rules without loading a separate skill — assume the working tree may contain user changes:
- Before broad edits, check the relevant git status/diff when possible.
- If user changes conflict with the task, work with them; ask only when the conflict blocks progress.
- Do not change git config, delete `.git`, run a global formatter, or mass-rename unless that is the task itself.
