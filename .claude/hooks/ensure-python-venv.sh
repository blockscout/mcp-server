#!/bin/bash
# PreToolUse hook: blocks bare Python tool invocations that bypass the project venv.
# Requires .venv/bin/<tool> or `uv run <tool>` to ensure consistent environment.
# Works with pipelines (|), sequences (;), and compound commands (&&).

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Allow everything inside devcontainer (tools are installed system-wide)
[ -f /.dockerenv ] && exit 0

# Block uv pip install --system (installs outside venv)
if printf '%s' "$COMMAND" | grep -qE 'uv pip install.*--system'; then
    echo "uv pip install --system bypasses the project venv. Use: uv pip install --python .venv \"<package>\"" >&2
    exit 2
fi

# Remove known-safe invocations before scanning for bare tools.
# This prevents false negatives like: `.venv/bin/python -V; pytest`
# or `uv run pytest tests/ && python -V` from slipping through.
SANITIZED=$(printf '%s' "$COMMAND" \
    | sed -E 's/\.venv\/bin\/(python3?|pytest|ruff)[[:space:]]?//g' \
    | sed -E 's/uv run (python3?|pytest|ruff)[[:space:]]?//g')

# Block bare tool invocations anywhere in the sanitized command
if printf '%s' "$SANITIZED" | grep -qE '(^|[[:space:];&|])(python3?|pytest|ruff)([[:space:]]|$)'; then
    cat >&2 <<'EOF'
Bare Python tool detected. Use the project venv instead:
  .venv/bin/<tool> ...    (direct path)
  uv run <tool> ...       (via uv, also works in worktrees)
EOF
    exit 2
fi

exit 0
