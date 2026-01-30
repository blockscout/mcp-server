#!/usr/bin/env python3
"""
PreToolUse hook to automatically approve Bash mkdir operations for the temp/ directory.

This hook is designed to be used in skill frontmatter to eliminate permission
prompts when skills create directories in their designated temp/ output directories.

Usage in skill frontmatter:
  hooks:
    PreToolUse:
      - matcher: "Bash"
        hooks:
          - type: command
            command: "$CLAUDE_PROJECT_DIR/.claude/hooks/allow-temp-dirs.py"
"""

import json
import re
import sys


def is_temp_mkdir_command(command: str) -> bool:
    """
    Check if the Bash command is creating directories within the temp/ directory.

    Handles various mkdir patterns:
    - mkdir temp/subdir
    - mkdir -p temp/subdir
    - mkdir -p temp/gh_issues
    - mkdir -p ./temp/impl_plans
    """
    if not command:
        return False

    # Normalize whitespace
    normalized = " ".join(command.split())

    # Check if it's a mkdir command
    if not normalized.startswith("mkdir"):
        return False

    # Extract the path argument (handles -p flag and other options)
    # Pattern: mkdir [-p] [other flags] path
    match = re.search(r"mkdir\s+(?:-[a-z]+\s+)*([^\s]+)", normalized)
    if not match:
        return False

    path = match.group(1)

    # Normalize path separators
    normalized_path = path.replace("\\", "/")

    # Check if path is within temp/ directory
    return normalized_path.startswith("temp/") or normalized_path.startswith("./temp/") or "/temp/" in normalized_path


def main():
    try:
        # Read hook input from stdin
        data = json.load(sys.stdin)

        # Extract command from tool input
        command = data.get("tool_input", {}).get("command", "")

        # Check if the command is creating a temp/ directory
        if is_temp_mkdir_command(command):
            # Auto-approve the mkdir operation
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Auto-approved: skill creates directory in temp/",
                }
            }
            print(json.dumps(output))

        # For non-temp mkdir commands, exit cleanly without output
        # This allows normal permission flow to proceed
        sys.exit(0)

    except Exception:
        # On any error, exit cleanly to let normal permission flow proceed
        # We don't want to break tool execution due to hook failures
        sys.exit(0)


if __name__ == "__main__":
    main()
