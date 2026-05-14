#!/bin/bash
# PreToolUse hook: blocks bare Python tool invocations that bypass the project venv.
# Requires .venv/bin/<tool> or `uv run <tool>` to ensure consistent environment.
# Works with pipelines (|), sequences (;), and compound commands (&&).

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Allow if already using venv path or uv run
if printf '%s' "$COMMAND" | grep -qE '(\.venv/bin/|uv run )'; then
    exit 0
fi

# Block bare tool invocations anywhere in the command (after |, ;, &&, or at start)
if printf '%s' "$COMMAND" | grep -qE '(^|[[:space:];&|])(python3?|pytest|ruff)([[:space:]]|$)'; then
    cat >&2 <<'EOF'
Bare Python tool detected. Use the project venv instead:
  .venv/bin/<tool> ...    (direct path)
  uv run <tool> ...       (via uv, also works in worktrees)
EOF
    exit 2
fi

# Block uv pip install --system (installs outside venv)
if printf '%s' "$COMMAND" | grep -qE 'uv pip install.*--system|uv pip install.*-p[[:space:]]*system'; then
    echo "uv pip install --system bypasses the project venv. Use: uv pip install --python .venv \"<package>\"" >&2
    exit 2
fi

exit 0
