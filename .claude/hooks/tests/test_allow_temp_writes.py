"""
Unit tests for the allow-temp-writes.py PreToolUse hook.

This hook auto-approves Write tool operations that target files within temp/,
but must reject any paths with security risks like absolute paths,
parent directory traversal, or paths with temp in the middle.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "allow-temp-writes.py"


def run_hook(file_path: str) -> dict | None:
    """
    Run the hook with a given file path and return the parsed output.

    Returns None if the hook produces no output (allowing normal permission flow).
    """
    hook_input = {
        "tool_input": {
            "file_path": file_path,
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


class TestValidPaths:
    """Test cases for file paths that should be auto-approved."""

    def test_simple_temp_file(self):
        """Should approve: temp/output.md"""
        output = run_hook("temp/output.md")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_temp_file_with_subdirs(self):
        """Should approve: temp/subdir/data.json"""
        output = run_hook("temp/subdir/data.json")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_temp_file_with_dot_prefix(self):
        """Should approve: ./temp/report.txt"""
        output = run_hook("./temp/report.txt")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_temp_file_nested_dirs(self):
        """Should approve: temp/a/b/c/file.md"""
        output = run_hook("temp/a/b/c/file.md")
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestPathTraversalAndAbsolutePaths:
    """Test cases for path traversal and absolute path security scenarios."""

    def test_reject_path_traversal_to_other_project(self):
        """Should reject: ../other-project/temp/data.json"""
        output = run_hook("../other-project/temp/data.json")
        assert output is None, "Hook should not approve path traversal to other directories"

    def test_reject_path_traversal_upward(self):
        """Should reject: ../../secrets/temp/config.yaml"""
        output = run_hook("../../secrets/temp/config.yaml")
        assert output is None, "Hook should not approve upward path traversal"

    def test_reject_absolute_path_with_temp_in_middle(self):
        """Should reject: /etc/malicious/temp/evil.txt"""
        output = run_hook("/etc/malicious/temp/evil.txt")
        assert output is None, "Hook should not approve absolute paths with temp in middle"

    def test_reject_absolute_path_system_dir(self):
        """Should reject: /var/log/temp/data.log"""
        output = run_hook("/var/log/temp/data.log")
        assert output is None, "Hook should not approve absolute paths to system directories"

    def test_reject_parent_references_escaping_temp(self):
        """Should reject: temp/../../../etc/shadow"""
        output = run_hook("temp/../../../etc/shadow")
        assert output is None, "Hook should not approve paths with parent references escaping temp"

    def test_reject_parent_references_to_passwd(self):
        """Should reject: temp/../../../../../../etc/passwd"""
        output = run_hook("temp/../../../../../../etc/passwd")
        assert output is None, "Hook should not approve parent references to system files"

    def test_reject_complex_parent_traversal(self):
        """Should reject: ./temp/../../../usr/local/bin/malware"""
        output = run_hook("./temp/../../../usr/local/bin/malware")
        assert output is None, "Hook should not approve complex parent directory traversal"

    def test_reject_absolute_home_with_temp(self):
        """Should reject: /home/user/temp/file.txt"""
        output = run_hook("/home/user/temp/file.txt")
        assert output is None, "Hook should not approve absolute paths even in user home"

    def test_reject_mixed_traversal(self):
        """Should reject: temp/subdir/../../../../../../bin/sh"""
        output = run_hook("temp/subdir/../../../../../../bin/sh")
        assert output is None, "Hook should not approve mixed traversal patterns"


class TestNonTempPaths:
    """Test cases for paths that don't target temp/ directory."""

    def test_ignore_non_temp_file(self):
        """Should not approve: src/main.py"""
        output = run_hook("src/main.py")
        assert output is None, "Hook should not approve non-temp file paths"

    def test_ignore_root_file(self):
        """Should not approve: README.md"""
        output = run_hook("README.md")
        assert output is None, "Hook should not approve root directory files"

    def test_ignore_home_directory(self):
        """Should not approve: ~/documents/file.txt"""
        output = run_hook("~/documents/file.txt")
        assert output is None, "Hook should not approve home directory paths"

    def test_ignore_absolute_path(self):
        """Should not approve: /etc/config.json"""
        output = run_hook("/etc/config.json")
        assert output is None, "Hook should not approve absolute non-temp paths"

    def test_ignore_similar_name(self):
        """Should not approve: temporary/file.txt"""
        output = run_hook("temporary/file.txt")
        assert output is None, "Hook should not approve paths with similar names"


class TestEdgeCases:
    """Test cases for edge cases and special scenarios."""

    def test_ignore_empty_path(self):
        """Should not approve: empty string"""
        output = run_hook("")
        assert output is None, "Hook should handle empty paths gracefully"

    def test_temp_only_no_file(self):
        """Should approve: temp/ (directory reference)"""
        # This is edge case - in practice Write tool requires a file
        # but the validation should be consistent
        output = run_hook("temp/")
        assert output is not None, "Hook should approve temp/ directory reference"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
