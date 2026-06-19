#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-Blockscout
#
# Reset the new-findings directory for an implementation plan feedback review.
#
# The review-plan-findings-feedback skill writes only newly discovered findings
# into <repo>/.ai/impl_plans/<plan-id>-findings/. Resetting the directory at the
# start of every run prevents stale findings from a previous feedback round from
# being mistaken for current output.

set -euo pipefail

plan_id="${1:-}"

if [[ -z "$plan_id" ]]; then
  echo "usage: $(basename "$0") <plan-id> [impl-plans-dir]" >&2
  exit 2
fi

if [[ ! "$plan_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "error: invalid plan id '$plan_id' (expected a single segment like 'issue-418')" >&2
  exit 2
fi

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "error: not inside a git repository (run within the project checkout or a git worktree)" >&2
  exit 5
fi

impl_plans_dir="${2:-$repo_root/.ai/impl_plans}"

plan_file="$impl_plans_dir/$plan_id.md"
if [[ ! -f "$plan_file" ]]; then
  echo "error: plan file $plan_file not found -- is the plan id '$plan_id' correct?" >&2
  exit 3
fi

findings_dir="$impl_plans_dir/$plan_id-findings"
if [[ -e "$findings_dir" && ! -d "$findings_dir" ]]; then
  echo "error: $findings_dir exists but is not a directory" >&2
  exit 4
fi

rm -rf "$findings_dir"
mkdir -p "$findings_dir"

( cd "$findings_dir" && pwd )
