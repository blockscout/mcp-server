#!/usr/bin/env python3
"""
PreToolUse hook to automatically approve Write operations to the temp/ directory.

This hook is designed to be used in skill frontmatter to eliminate permission
prompts when skills create files in their designated temp/ output directories.

Usage in skill frontmatter:
  hooks:
    PreToolUse:
      - matcher: "Write"
        hooks:
          - type: command
            command: "$CLAUDE_PROJECT_DIR/.claude/hooks/allow-temp-writes.py"
"""

import json
import os
import sys


def is_temp_path(file_path: str) -> bool:
    """
    Check if the file path is within the temp/ directory.

    Handles various path formats:
    - temp/file.md (relative from project root)
    - ./temp/file.md (explicit relative)
    - /absolute/path/to/project/temp/file.md (absolute within project)

    Security: Rejects paths with:
    - Absolute paths outside the project directory
    - Path traversal (../other-project/temp/data.json)
    - Parent references (temp/../../../etc/shadow)
    """
    if not file_path:
        return False

    # Normalize path separators for consistency
    normalized = file_path.replace("\\", "/")

    # Reject any path containing parent directory references
    if ".." in normalized:
        return False

    # Handle absolute paths: allow if within CLAUDE_PROJECT_DIR/temp/
    if normalized.startswith("/"):
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
        if project_dir:
            project_temp = f"{project_dir.rstrip('/')}/temp/"
            if normalized.startswith(project_temp):
                return True
        return False

    # Only allow paths that start with temp/ or ./temp/
    # This ensures we're writing files within the temp/ directory
    return normalized.startswith("temp/") or normalized.startswith("./temp/")


def main():
    try:
        # Read hook input from stdin
        data = json.load(sys.stdin)

        # Extract file path from tool input
        file_path = data.get("tool_input", {}).get("file_path", "")

        # Check if the file path is within temp/ directory
        if is_temp_path(file_path):
            # Auto-approve the write operation
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Auto-approved: skill writes to temp/ directory",
                }
            }
            print(json.dumps(output))

        # For non-temp paths, exit cleanly without output
        # This allows normal permission flow to proceed
        sys.exit(0)

    except Exception:
        # On any error, exit cleanly to let normal permission flow proceed
        # We don't want to break tool execution due to hook failures
        sys.exit(0)


if __name__ == "__main__":
    main()
