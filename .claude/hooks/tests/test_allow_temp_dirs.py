"""
Unit tests for the allow-temp-dirs.py PreToolUse hook.

This hook auto-approves mkdir commands that create directories within temp/,
but must reject any commands with security risks like multiple paths,
shell operators, or command substitution.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "allow-temp-dirs.py"


def run_hook(command: str) -> dict | None:
    """
    Run the hook with a given Bash command and return the parsed output.

    Returns None if the hook produces no output (allowing normal permission flow).
    """
    hook_input = {
        "tool_input": {
            "command": command,
        }
    }

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test_hook_exists():
    """Verify the hook file exists and is executable."""
    assert HOOK_PATH.exists(), f"Hook not found at {HOOK_PATH}"


class TestValidCommands:
    """Test cases for commands that should be auto-approved."""

    def test_simple_temp_mkdir(self):
        """Should approve: mkdir temp/subdir"""
        output = run_hook("mkdir temp/subdir")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_mkdir_with_p_flag(self):
        """Should approve: mkdir -p temp/nested/subdir"""
        output = run_hook("mkdir -p temp/nested/subdir")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_mkdir_with_dot_prefix(self):
        """Should approve: mkdir -p ./temp/subdir"""
        output = run_hook("mkdir -p ./temp/subdir")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_mkdir_with_mode_flag(self):
        """Should approve: mkdir -m 755 temp/subdir"""
        output = run_hook("mkdir -m 755 temp/subdir")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_mkdir_with_multiple_flags(self):
        """Should approve: mkdir -p -m 755 temp/subdir"""
        output = run_hook("mkdir -p -m 755 temp/subdir")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestSecurityRejections:
    """Test cases for commands that should be rejected for security reasons."""

    def test_reject_multiple_paths(self):
        """Should reject: mkdir temp/ok /etc"""
        output = run_hook("mkdir temp/ok /etc")
        assert output is None, "Hook should not approve commands with multiple paths"

    def test_reject_multiple_paths_with_flag(self):
        """Should reject: mkdir -p temp/ok /etc"""
        output = run_hook("mkdir -p temp/ok /etc")
        assert output is None, "Hook should not approve commands with multiple paths"

    def test_reject_and_operator(self):
        """Should reject: mkdir temp/ok && mkdir /etc"""
        output = run_hook("mkdir temp/ok && mkdir /etc")
        assert output is None, "Hook should not approve commands with && operator"

    def test_reject_or_operator(self):
        """Should reject: mkdir temp/ok || mkdir /etc"""
        output = run_hook("mkdir temp/ok || mkdir /etc")
        assert output is None, "Hook should not approve commands with || operator"

    def test_reject_semicolon_separator(self):
        """Should reject: mkdir temp/ok; mkdir /etc"""
        output = run_hook("mkdir temp/ok; mkdir /etc")
        assert output is None, "Hook should not approve commands with ; separator"

    def test_reject_pipe_operator(self):
        """Should reject: mkdir temp/ok | tee /etc/evil"""
        output = run_hook("mkdir temp/ok | tee /etc/evil")
        assert output is None, "Hook should not approve commands with | operator"

    def test_reject_command_substitution_dollar(self):
        """Should reject: mkdir temp/$(malicious)"""
        output = run_hook("mkdir temp/$(malicious)")
        assert output is None, "Hook should not approve commands with $() substitution"

    def test_reject_command_substitution_backtick(self):
        """Should reject: mkdir temp/`malicious`"""
        output = run_hook("mkdir temp/`malicious`")
        assert output is None, "Hook should not approve commands with backtick substitution"

    def test_reject_output_redirection(self):
        """Should reject: mkdir temp/ok > /etc/evil"""
        output = run_hook("mkdir temp/ok > /etc/evil")
        assert output is None, "Hook should not approve commands with output redirection"

    def test_reject_input_redirection(self):
        """Should reject: mkdir temp/ok < /etc/passwd"""
        output = run_hook("mkdir temp/ok < /etc/passwd")
        assert output is None, "Hook should not approve commands with input redirection"

    def test_reject_variable_expansion(self):
        """Should reject: mkdir temp/$EVIL"""
        output = run_hook("mkdir temp/$EVIL")
        assert output is None, "Hook should not approve commands with variable expansion"

    def test_reject_brace_expansion(self):
        """Should reject: mkdir temp/{ok,/etc}"""
        output = run_hook("mkdir temp/{ok,/etc}")
        assert output is None, "Hook should not approve commands with brace expansion"


class TestNonTempCommands:
    """Test cases for commands that don't target temp/ directory."""

    def test_ignore_non_temp_mkdir(self):
        """Should not approve: mkdir /etc/evil"""
        output = run_hook("mkdir /etc/evil")
        assert output is None, "Hook should not approve non-temp directories"

    def test_ignore_home_mkdir(self):
        """Should not approve: mkdir ~/somedir"""
        output = run_hook("mkdir ~/somedir")
        assert output is None, "Hook should not approve home directory paths"

    def test_ignore_relative_non_temp(self):
        """Should not approve: mkdir src/newdir"""
        output = run_hook("mkdir src/newdir")
        assert output is None, "Hook should not approve non-temp relative paths"


class TestNonMkdirCommands:
    """Test cases for non-mkdir commands."""

    def test_ignore_ls_command(self):
        """Should not approve: ls temp/"""
        output = run_hook("ls temp/")
        assert output is None, "Hook should only handle mkdir commands"

    def test_ignore_rm_command(self):
        """Should not approve: rm -rf temp/"""
        output = run_hook("rm -rf temp/")
        assert output is None, "Hook should only handle mkdir commands"

    def test_ignore_empty_command(self):
        """Should not approve: empty string"""
        output = run_hook("")
        assert output is None, "Hook should handle empty commands gracefully"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
