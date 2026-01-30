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
import sys


def is_temp_mkdir_command(command: str) -> bool:
    """
    Check if the Bash command is creating directories within the temp/ directory.

    Handles various mkdir patterns:
    - mkdir temp/subdir
    - mkdir -p temp/subdir
    - mkdir -p temp/gh_issues
    - mkdir -p ./temp/impl_plans

    Security: Rejects commands with:
    - Multiple paths (mkdir temp/ok /etc)
    - Shell operators (mkdir temp/ok && rm -rf /)
    - Command substitution (mkdir temp/$(malicious))
    - Redirections or other shell metacharacters
    """
    if not command:
        return False

    # Normalize whitespace
    normalized = " ".join(command.split())

    # Check if it's a mkdir command
    if not normalized.startswith("mkdir"):
        return False

    # Reject commands with shell operators or metacharacters
    dangerous_chars = ["&&", "||", ";", "|", "$(", "`", ">", "<", "$", "{", "}"]
    if any(char in command for char in dangerous_chars):
        return False

    # Extract all arguments after flags
    # Pattern: mkdir [-p] [other flags] path1 [path2...]
    parts = normalized.split()
    paths = []
    skip_next = False

    for part in parts[1:]:  # Skip "mkdir"
        if skip_next:
            skip_next = False
            continue
        if part.startswith("-"):
            # Check if this flag takes an argument (like -m mode)
            if part in ["-m", "--mode", "-Z", "--context"]:
                skip_next = True
            continue
        # This is a path argument
        paths.append(part)

    # Must have exactly one path
    if len(paths) != 1:
        return False

    path = paths[0]

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
