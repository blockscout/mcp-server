# Hook Tests

This directory contains tests for Claude Code hooks used in this project.

## Running Tests

These tests are separate from the main MCP server test suite and don't run by default.

To run hook tests:

```bash
# Run all hook tests
pytest .claude/hooks/tests/

# Run a specific hook test file
pytest .claude/hooks/tests/test_allow_temp_dirs.py

# Run with verbose output
pytest .claude/hooks/tests/ -v
```

## Test Files

- `test_allow_temp_dirs.py` - Tests for the `allow-temp-dirs.py` PreToolUse hook that auto-approves mkdir operations for temp/ directories while rejecting security risks.
