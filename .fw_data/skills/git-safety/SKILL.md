---
name: git-safety
description: Git and working-tree workflow rules — inspecting status/diff before broad edits, handling conflicts with user changes, restrictions on git config/formatters/mass-rename. Use when the task touches git history, branches, or a working tree that may have pending changes.
---

# Git and user changes
Assume the working tree may contain user changes.
- Never revert, overwrite, or clean unrelated changes unless explicitly asked.
- Before broad edits, inspect relevant git status/diff when available.
- If user changes conflict with the task, work with them; ask only if the conflict blocks progress.
- No git config changes, `.git` deletion, global formatters, mass-rename unless that IS the task.
