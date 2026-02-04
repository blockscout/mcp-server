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


def run_hook(command: str, env: dict | None = None) -> dict | None:
    """
    Run the hook with a given Bash command and return the parsed output.

    Returns None if the hook produces no output (allowing normal permission flow).

    Args:
        command: The Bash command to test
        env: Optional environment variables to pass to the hook
    """
    hook_input = {
        "tool_input": {
            "command": command,
        }
    }

    # Merge with current environment if custom env provided
    run_env = None
    if env:
        import os

        run_env = os.environ.copy()
        run_env.update(env)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        check=False,
        env=run_env,
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


class TestPathTraversalAndAbsolutePaths:
    """Test cases for path traversal and absolute path security scenarios."""

    def test_reject_path_traversal_to_other_project(self):
        """Should reject: mkdir ../other-project/temp/data"""
        output = run_hook("mkdir ../other-project/temp/data")
        assert output is None, "Hook should not approve path traversal to other directories"

    def test_reject_path_traversal_with_flag(self):
        """Should reject: mkdir -p ../other-project/temp/data"""
        output = run_hook("mkdir -p ../other-project/temp/data")
        assert output is None, "Hook should not approve path traversal even with -p flag"

    def test_reject_absolute_path_with_temp_in_middle(self):
        """Should reject: mkdir /etc/malicious/temp/subdir (outside project)"""
        output = run_hook("mkdir /etc/malicious/temp/subdir")
        assert output is None, "Hook should not approve absolute paths outside project"

    def test_reject_absolute_path_with_temp_and_flag(self):
        """Should reject: mkdir -p /var/log/temp/data (outside project)"""
        output = run_hook("mkdir -p /var/log/temp/data")
        assert output is None, "Hook should not approve absolute paths outside project"

    def test_reject_parent_references_escaping_temp(self):
        """Should reject: mkdir temp/../../../etc/shadow"""
        output = run_hook("mkdir temp/../../../etc/shadow")
        assert output is None, "Hook should not approve paths with parent references escaping temp"

    def test_reject_parent_references_with_flag(self):
        """Should reject: mkdir -p temp/../../../../../../etc/passwd"""
        output = run_hook("mkdir -p temp/../../../../../../etc/passwd")
        assert output is None, "Hook should not approve parent references even with -p flag"

    def test_reject_complex_parent_traversal(self):
        """Should reject: mkdir ./temp/../../../usr/local/bin"""
        output = run_hook("mkdir ./temp/../../../usr/local/bin")
        assert output is None, "Hook should not approve complex parent directory traversal"


class TestAbsolutePathsWithProjectDir:
    """Test cases for absolute paths within CLAUDE_PROJECT_DIR."""

    def test_approve_absolute_path_in_project_temp(self):
        """Should approve: mkdir /workspaces/project/temp/subdir with matching CLAUDE_PROJECT_DIR"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project"}
        output = run_hook("mkdir /workspaces/project/temp/subdir", env=env)
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_approve_absolute_path_with_p_flag(self):
        """Should approve: mkdir -p /workspaces/project/temp/nested/dir"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project"}
        output = run_hook("mkdir -p /workspaces/project/temp/nested/dir", env=env)
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_approve_absolute_path_deeply_nested(self):
        """Should approve: mkdir -p /home/user/myproject/temp/a/b/c"""
        env = {"CLAUDE_PROJECT_DIR": "/home/user/myproject"}
        output = run_hook("mkdir -p /home/user/myproject/temp/a/b/c", env=env)
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_reject_absolute_path_outside_project(self):
        """Should reject: mkdir /other/project/temp/subdir (different project)"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project"}
        output = run_hook("mkdir /other/project/temp/subdir", env=env)
        assert output is None, "Hook should not approve paths outside project directory"

    def test_reject_absolute_path_no_project_dir_set(self):
        """Should reject: mkdir /workspaces/project/temp/subdir without CLAUDE_PROJECT_DIR"""
        # Don't set CLAUDE_PROJECT_DIR - hook should reject all absolute paths
        output = run_hook("mkdir /workspaces/project/temp/subdir", env={})
        assert output is None, "Hook should reject absolute paths when CLAUDE_PROJECT_DIR not set"

    def test_reject_absolute_path_not_in_temp(self):
        """Should reject: mkdir /workspaces/project/src/newdir (not in temp/)"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project"}
        output = run_hook("mkdir /workspaces/project/src/newdir", env=env)
        assert output is None, "Hook should not approve paths outside temp/ directory"

    def test_reject_absolute_path_with_traversal(self):
        """Should reject: mkdir /workspaces/project/temp/../../../etc"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project"}
        output = run_hook("mkdir /workspaces/project/temp/../../../etc", env=env)
        assert output is None, "Hook should reject paths with traversal even within project"

    def test_project_dir_with_trailing_slash(self):
        """Should approve with trailing slash in CLAUDE_PROJECT_DIR"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project/"}
        output = run_hook("mkdir /workspaces/project/temp/subdir", env=env)
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_approve_absolute_with_mode_flag(self):
        """Should approve: mkdir -m 755 /workspaces/project/temp/subdir"""
        env = {"CLAUDE_PROJECT_DIR": "/workspaces/project"}
        output = run_hook("mkdir -m 755 /workspaces/project/temp/subdir", env=env)
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


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
