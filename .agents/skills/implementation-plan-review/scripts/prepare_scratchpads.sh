#!/usr/bin/env bash
#
# Prepare a clean scratchpad directory for implementation-plan-review.
#
# Usage:
#   prepare_scratchpads.sh <plan-file>
#
# Output on success:
#   OK <scratchpad-path>
#
# Output on failure:
#   ERROR <message>

set -euo pipefail

if [[ $# -ne 1 || -z "${1:-}" ]]; then
  echo "ERROR usage: $(basename "$0") <plan-file>" >&2
  exit 1
fi

plan_file="$1"
plan_dir="$(dirname -- "$plan_file")"
plan_base="$(basename -- "$plan_file")"

if [[ "$plan_base" == "" || "$plan_base" == "." || "$plan_base" == ".." ]]; then
  echo "ERROR Unsafe plan filename: $plan_file" >&2
  exit 2
fi

if [[ ! -d "$plan_dir" ]]; then
  echo "ERROR Plan parent directory does not exist or is not a directory: $plan_dir" >&2
  exit 2
fi

if [[ ! -f "$plan_file" ]]; then
  echo "ERROR Plan file does not exist or is not a file: $plan_file" >&2
  exit 2
fi

plan_stem="$plan_base"
if [[ "$plan_stem" == *.* && "$plan_stem" != .* ]]; then
  plan_stem="${plan_stem%.*}"
fi

scratchpad_name="${plan_stem}-scratchpads"
if [[ "$plan_stem" == "" || "$scratchpad_name" == "" || "$scratchpad_name" == "." || "$scratchpad_name" == ".." || "$scratchpad_name" != *"-scratchpads" ]]; then
  echo "ERROR Unsafe scratchpad directory name derived from: $plan_base" >&2
  exit 2
fi

scratchpad_dir="$plan_dir/$scratchpad_name"

if [[ -L "$scratchpad_dir" ]]; then
  echo "ERROR Refusing to remove symlink scratchpad path: $scratchpad_dir" >&2
  exit 2
fi

if [[ -e "$scratchpad_dir" && ! -d "$scratchpad_dir" ]]; then
  echo "ERROR Scratchpad path exists and is not a directory: $scratchpad_dir" >&2
  exit 2
fi

rm -rf -- "$scratchpad_dir"
mkdir -- "$scratchpad_dir"

echo "OK $scratchpad_dir"
