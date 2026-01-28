#!/bin/bash

echo "<memory_file path=\".cursor/rules/000-role-and-task.mdc\">"
cat ${CLAUDE_PROJECT_DIR}/.cursor/rules/000-role-and-task.mdc
echo "</memory_file>"

echo "<memory_file path=\".cursor/rules/010-implementation-rules.mdc\">"
cat ${CLAUDE_PROJECT_DIR}/.cursor/rules/010-implementation-rules.mdc
echo "</memory_file>"

# Find all AGENTS.md files in current directory and subdirectories
# This is a temporay solution for case that Claude Code not satisfies with AGENTS.md usage case. 
find "$CLAUDE_PROJECT_DIR" -name "AGENTS.md" -type f | \
    awk -v root="$CLAUDE_PROJECT_DIR/AGENTS.md" '{if ($0 == root) print $0; else files[++n]=$0} END {for (i=1; i<=n; i++) if (files[i] != root) print files[i]}' | \
    while read -r file; do
    # Remove the $CLAUDE_PROJECT_DIR prefix from $file for memory_file path
    rel_path="${file#${CLAUDE_PROJECT_DIR}/}"
    echo "<memory_file path=\"$rel_path\">"
    cat "$file"
    echo "</memory_file>"
done
