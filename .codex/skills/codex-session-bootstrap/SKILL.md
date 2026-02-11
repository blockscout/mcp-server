---
name: codex-session-bootstrap
description: Codex-only mandatory startup skill for this repository. Trigger for every user request in this project, including read-only questions, planning, and code changes. Run before any reasoning, shell commands, or file edits.
---

# Codex Session Bootstrap

Execute this sequence at the beginning of every session, with no exceptions:

1. Read `.cursor/AGENTS.md` in full.
2. Read `.cursor/rules/000-role-and-task.mdc` in full.
3. Read `.cursor/rules/010-implementation-rules.mdc` in full.

Apply these constraints:

- Complete the reads before any planning, file edits, code execution, or implementation work.
- Do not skip the sequence even if the user request seems unrelated.
- If a read fails, resolve the failure first and then restart the sequence from step 1.
