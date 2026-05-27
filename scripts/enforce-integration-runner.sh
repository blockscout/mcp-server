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

# Block a pytest invocation that targets the integration tests in either of the
# two ways one can reach them:
#   1. the integration marker — `-m[[:space:]]+['\"]?integration` matches
#      `-m integration`, `-m "integration"`, `-m 'integration and ...'`, but NOT
#      the default unit run `-m "not integration"` (there "not" follows the
#      quote) nor the runner's own `--marker integration` (no whitespace after
#      the `-m` in `--marker`);
#   2. a `tests/integration` path target — e.g. `pytest tests/integration/...`
#      or `uv run pytest tests/integration/transaction`, which select the same
#      tests without the marker. (`tests/integration` holds only integration
#      tests, so any pytest aimed there must go through the runner.) The normal
#      unit runs `pytest` / `pytest tests/` / `pytest -m "not integration"` do
#      not contain that literal path, so they are unaffected.
# This is a string heuristic, not a parser: exotic bypasses (cd into the dir,
# wrapper scripts, indirect conftest collection) are a known limitation —
# closing them fully would need runtime/AST interception, which is not worth it.
if printf '%s' "$COMMAND" | grep -qE 'pytest' \
   && printf '%s' "$COMMAND" | grep -qE "(\-m[[:space:]]+['\"]?integration|tests/integration)"; then
    cat >&2 <<'EOF'
Direct integration-test run blocked.

Running the integration tests straight through pytest (whether via `-m
integration` or a `tests/integration/...` path target) has no hard HTTP timeout,
so one unresponsive endpoint can hang the run (and you) indefinitely.

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
