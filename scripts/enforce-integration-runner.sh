#!/bin/bash
# Tool-call gate: blocks direct integration-test runs so they always go through
# the timeout-protected runner (scripts/run_integration_tests.py, documented by
# the run-integration-tests skill).
#
# Why: integration tests make real network calls and the HTTP client has no hard
# request timeout. A plain `pytest -m integration` can hang indefinitely on an
# unresponsive endpoint and block the agent. The runner isolates each test in
# its own subprocess with a per-test timeout, kills hangs, and returns a bounded
# report. The runner shells out to pytest internally via a subprocess, so that
# pytest invocation never passes through the agent's shell tool and is not seen
# here.
#
# This script lives in scripts/ (not under any single agent's config dir) so the
# gate logic — which commands to block and the message to show — can be reused
# across agents. Wire it up as a pre-shell-command hook in whichever agent you
# use. The one agent-specific assumption is the input contract below: it reads
# the proposed command from a JSON object on stdin at `.tool_input.command`
# (Claude Code's PreToolUse hook format). For an agent with a different hook
# payload, adapt only that extraction line; the block logic stays the same.

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Always allow the runner itself (it is the sanctioned way to run these tests).
if printf '%s' "$COMMAND" | grep -qE 'run_integration_tests\.py|run-integration-tests'; then
    exit 0
fi

# Block only when the command both invokes pytest AND selects the integration
# marker. The `-m[[:space:]]+['\"]?integration` pattern matches `-m integration`,
# `-m "integration"`, and `-m 'integration and ...'`, but NOT the default unit
# run `-m "not integration"` (there "not" follows the quote) nor the runner's
# own `--marker integration` (no whitespace after the `-m` in `--marker`).
if printf '%s' "$COMMAND" | grep -qE 'pytest' \
   && printf '%s' "$COMMAND" | grep -qE "\-m[[:space:]]+['\"]?integration"; then
    cat >&2 <<'EOF'
Direct integration-test run blocked.

`pytest -m integration` has no hard HTTP timeout, so one unresponsive endpoint
can hang the run (and you) indefinitely.

Use the `run-integration-tests` skill instead — it documents the timeout-
protected runner and how to scope it to the whole suite, a module, or a single
test. Consult that skill for the full instructions.

(Fallback if you cannot load the skill: run the project tool directly via the
venv, e.g.
`uv run python scripts/run_integration_tests.py [TARGET ...] [--timeout N]`.)
EOF
    exit 2
fi

exit 0
