#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-Blockscout
#
# Reset the findings-feedback directory for an implementation plan.
#
# The address-plan-findings skill writes one feedback file per run into
# <repo>/.ai/impl_plans/<plan-id>-findings-feedback/. That file must reflect
# only the current round of findings, never a stale artifact from a previous
# round, so the skill resets the directory before doing any work. This script
# is that reset: it removes the directory if present and recreates it empty.
#
# Directory-agnostic: it resolves the project root from `git rev-parse
# --show-toplevel` rather than trusting the caller's cwd, so it behaves the same
# in the principal checkout and in a linked `git worktree` (in each case the
# toplevel is that tree's own root, where its .ai/impl_plans lives). It uses the
# cwd's toplevel -- where the agent is working -- not the script's own location.
#
# Guarded on purpose: it refuses a plan id that is not a single path segment,
# and refuses to run when the plan file itself is missing -- either would risk
# wiping or creating the wrong directory.
#
# Usage:  reset_findings_feedback.sh <plan-id> [impl-plans-dir]
#   e.g.  reset_findings_feedback.sh issue-418
#         -> resets <repo>/.ai/impl_plans/issue-418-findings-feedback/
#
# [impl-plans-dir] overrides the default <repo>/.ai/impl_plans and is used
# verbatim (absolute, or relative to cwd). On success the script prints the
# absolute path of the now-empty directory, so the caller knows where to write.

set -euo pipefail

plan_id="${1:-}"

if [[ -z "$plan_id" ]]; then
  echo "usage: $(basename "$0") <plan-id> [impl-plans-dir]" >&2
  exit 2
fi

# A plan id is one segment like "issue-418" -- never a path. Reject anything
# that could traverse out of the impl-plans dir and delete the wrong thing
# (this also rules out "", ".", ".." and any value containing "/" or "\").
if [[ ! "$plan_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "error: invalid plan id '$plan_id' (expected a single segment like 'issue-418')" >&2
  exit 2
fi

# Anchor to the project root so the right .ai/impl_plans is targeted regardless
# of the current working directory (principal checkout or git worktree alike).
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

feedback_dir="$impl_plans_dir/$plan_id-findings-feedback"
if [[ -e "$feedback_dir" && ! -d "$feedback_dir" ]]; then
  echo "error: $feedback_dir exists but is not a directory" >&2
  exit 4
fi

rm -rf "$feedback_dir"
mkdir -p "$feedback_dir"

# Print an absolute path (portable; avoids relying on realpath being installed).
( cd "$feedback_dir" && pwd )
