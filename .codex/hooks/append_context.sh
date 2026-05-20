#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(git rev-parse --show-toplevel)"

readonly CONTEXT_FILES=(
  ".cursor/AGENTS.md"
  ".cursor/rules/000-role-and-task.mdc"
  ".cursor/rules/010-implementation-rules.mdc"
)

for rel_path in "${CONTEXT_FILES[@]}"; do
  if [[ ! -f "${PROJECT_DIR}/${rel_path}" ]]; then
    printf '{"continue":false,"stopReason":"Required context file missing: %s","systemMessage":"Required context file missing: %s"}\n' "${rel_path}" "${rel_path}"
    exit 0
  fi
done

for rel_path in "${CONTEXT_FILES[@]}"; do
  printf '<memory_file path="%s">\n' "${rel_path}"
  cat "${PROJECT_DIR}/${rel_path}"
  printf '\n</memory_file>\n'
done
