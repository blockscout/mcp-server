#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-Blockscout
#
# Shared helper for the plan-review family of skill scripts:
#   implementation-plan-review/scripts/new_scratchpads_dir.sh
#   review-plan-findings-feedback/scripts/new_findings_dir.sh
#   address-plan-findings/scripts/new_feedback_dir.sh
#
# Source this file; it is not meant to be executed directly.
#
# Unified contract for every script that sources this library:
#   Success: stdout is exactly the absolute path of the newly created
#     directory, nothing else, no prefix. Exit code 0.
#   Failure: stderr is exactly one line, "error: <message>". Stdout empty.
#     Exit code:
#       2 - bad usage, or an invalid caller-supplied identifier/argument
#       3 - a required input file was not found (e.g. the plan file)
#       4 - the target directory path exists but is not a directory, or
#           could not be created
#       5 - not inside a git repository (only scripts that need git to
#           resolve the repo root use this code)
#
#   Every run creates a brand-new directory timestamped to the minute
#   (`date +%y%m%d-%H%M`, e.g. 260714-1022) and never deletes or reuses
#   an existing one. Two runs landing in the same calendar minute are not
#   disambiguated -- an accepted, deliberate simplicity trade-off.
#
# This library does NOT resolve a base directory from caller input.
# Turning a plan-id into a git-anchored `.ai/impl_plans/<plan-id>` base
# dir, vs. turning an arbitrary plan-file path into a `<dirname>/<stem>`
# base dir, are fundamentally different input shapes -- each wrapper
# resolves its own base_dir and category ("scratchpads" | "findings" |
# "findings-feedback"), routes its own validation errors through
# report_dir::die, and calls report_dir::new only for the final step.

report_dir::die() {
  local code="$1"
  shift
  echo "error: $*" >&2
  exit "$code"
}

# report_dir::new <base_dir> <category>
#   Creates <base_dir>/<category>/<timestamp> and prints its absolute path.
#   Caller must have already validated/sanitized base_dir; category is
#   always a fixed literal, never user input.
report_dir::new() {
  local base_dir="$1"
  local category="$2"
  local timestamp
  timestamp="$(date +%y%m%d-%H%M)"
  local target_dir="$base_dir/$category/$timestamp"

  if [[ -e "$target_dir" && ! -d "$target_dir" ]]; then
    report_dir::die 4 "target path exists and is not a directory: $target_dir"
  fi

  if ! mkdir -p -- "$target_dir" 2>/dev/null; then
    report_dir::die 4 "failed to create directory: $target_dir"
  fi

  ( cd -- "$target_dir" && pwd )
}
