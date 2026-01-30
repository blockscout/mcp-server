import json
import os
import sys
from pathlib import Path


def main():
    # 1. Read Input
    try:
        input_data = json.load(sys.stdin)
        args = input_data.get("tool_input", {})
        file_path_str = args.get("file_path")
    except Exception:
        # If we can't parse input, we deny to be safe
        print(json.dumps({"decision": "deny", "reason": "Hook error: Could not parse tool input."}))
        sys.exit(0)

    if not file_path_str:
        # If no file_path is provided for these tools, it's likely invalid usage anyway,
        # but technically we can't validate the path.
        # For write_file/replace, file_path is mandatory.
        print(json.dumps({"decision": "deny", "reason": "Hook error: No file_path provided in tool arguments."}))
        sys.exit(0)

    # 2. Resolve Paths
    try:
        current_working_dir = Path(os.getcwd()).resolve()
        # Handle cases where file_path might be absolute or relative
        target_path = Path(file_path_str)
        if not target_path.is_absolute():
            target_path = (current_working_dir / target_path).resolve()
        else:
            target_path = target_path.resolve()

        allowed_dir = (current_working_dir / "temp").resolve()
    except Exception as e:
        print(json.dumps({"decision": "deny", "reason": f"Hook error resolving paths: {str(e)}"}))
        sys.exit(0)

    # 3. Validation Logic
    # Check if target_path is relative to allowed_dir (i.e., inside it)
    is_allowed = False
    try:
        # relative_to throws ValueError if it's not a subpath
        target_path.relative_to(allowed_dir)
        is_allowed = True
    except ValueError:
        is_allowed = False

    if is_allowed:
        print(json.dumps({"decision": "continue"}))
    else:
        print(
            json.dumps(
                {
                    "decision": "deny",
                    "reason": (
                        "Operation denied. You are currently in 'research and plan' mode. "
                        "Modifying the codebase is strictly forbidden. "
                        "You may only create planning artifacts (e.g., plans, issue descriptions) "
                        "within the 'temp/' directory and its subdirectories."
                    ),
                }
            )
        )


if __name__ == "__main__":
    main()
