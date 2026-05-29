---
name: implement-plan
description: Use to implement a structured implementation plan (e.g. temp/impl_plans/issue-*.md) phase by phase. Trigger when the user asks to implement, execute, realize, or "do" an implementation-plan file. Orchestrates a phase-developer subagent and a plan-correspondence-verifier subagent for each phase, commits each verified phase, then walks the Final Checklist. Invoke explicitly — it makes commits and spawns many subagents.
disable-model-invocation: true
argument-hint: "[path-to-plan-file]"
---

# Implement Plan

Orchestrate the implementation of a structured implementation plan — the kind under `temp/impl_plans/` — **phase by phase**, using two subagents per phase. The plan file path is the argument to this skill (`$ARGUMENTS`); if none was given, ask the user which plan to implement.

## Your role

You are the **orchestrator**. You do **not** implement or verify anything yourself. You parse the plan, dispatch a `phase-developer` subagent to each phase, dispatch a `plan-correspondence-verifier` subagent to check it, loop until the phase is clean, commit it, and at the end walk the Final Checklist. Keeping implementation and verification in separate subagents — and out of your own context — is what keeps each run small, focused, and traceable.

## One rule above all: slice, never paraphrase

Cut the plan into pieces by its headings and pass those pieces **verbatim**. Never summarize, compress, or reword the plan's content before handing it down. The moment you paraphrase, you can silently drop a step — and then *both* the developer (who won't build it) and the verifier (who won't check it) inherit the loss. Your only transformation is mechanical slicing.

## The two subagents

- **`phase-developer`** (model: sonnet, full tooling) — implements one phase from its verbatim text. Defined in `.claude/agents/phase-developer.md`.
- **`plan-correspondence-verifier`** (model: opus, read-only) — checks that every step of a phase was actually done, honestly. It inspects the real diff and re-runs cheap checks; it is *not* a code reviewer. Defined in `.claude/agents/plan-correspondence-verifier.md`.

The exact text to pass each one is in [references/dispatch-templates.md](references/dispatch-templates.md). Read it before dispatching.

## Step 0 — Preconditions

1. Read the plan file. If the path wasn't provided, ask for it.
2. Check the current branch (`git branch --show-current`). If it is `main` (the default branch), **stop** and ask the user to create and check out a working branch first — this skill commits as it goes and must not commit onto `main`.
3. Check the working tree (`git status`). If there are unrelated uncommitted changes, surface them and confirm with the user before proceeding, so per-phase commits stay clean.

## Step 1 — Parse the plan mechanically

Split by headings:

- **Preamble** = everything before `## Phase 1` (Overview, Applicable Guidelines, Definition of Done — Test Integrity, Ordering/Environment notes). This binds every phase and goes to every subagent.
- **Phases** = each `## Phase N: ...` block, in order, with all subsections intact.
- **Final Checklist** = the `## Final Checklist` block.
- Also capture the **one-line title of each phase** (the `## Phase N: <title>` line) to pass as cross-reference context.

If the plan doesn't match this shape, don't guess — report what you found and ask the user how to proceed.

## Step 2 — Implement each phase, in order

Phases are sequential; never start phase N+1 before phase N is committed (the plan's ordering often depends on it). For each phase:

1. **Record the baseline**: `git rev-parse HEAD` — the ref the verifier diffs against for this phase. Capture it *before* dispatching the developer.
2. **Dispatch a fresh `phase-developer`** with the first-round brief from the templates file (preamble + this phase verbatim + other-phase titles + baseline note). Wait for its report.
3. **Dispatch a fresh `plan-correspondence-verifier`** with its brief (preamble + this phase verbatim + the baseline ref). Read its verdict.
4. **Branch on the verdict:**
   - `COMPLETE` → go to step 5.
   - `GAPS_FOUND` → dispatch a **fresh** `phase-developer` with the gap-round brief: the same context plus the verifier's gap list verbatim and "your prior work is already in the working tree; close exactly these gaps." Then go back to step 3 to re-verify.
5. **Bound the loop.** Allow at most **3** developer↔verifier rounds for a phase. If the verifier still reports gaps after the 3rd round — or if a developer reports it *cannot* complete a step — **stop and escalate to the user**: show the latest developer report and the verifier's outstanding gaps, and ask how to proceed. Never commit an unverified phase.
6. **Commit the phase** on the current branch once the verdict is `COMPLETE`. Use a message like `Phase <N>: <phase title>`. Do **not** push and do **not** open a PR — leave the branch for the user to review. End the commit message with the harness `Co-Authored-By` trailer.
7. Keep the developer's final report; you'll summarize all of them at the end.

Each phase = one commit. A fresh developer every round is intentional: all state lives in the git working tree, so a new subagent loses nothing and stays focused on exactly the open gaps.

## Step 3 — Final Checklist

After all phases are committed, walk the `## Final Checklist`. Classify each item:

- **Runnable check** (essentially a command — `grep`, `pytest`, `ruff check`, `ruff format --check`, or a full integration run via `python scripts/run_integration_tests.py tests/integration/`): run it yourself and read the result. This is where the **full integration suite gets its one authoritative independent run.**
- **Inspectable claim** (e.g. "documentation updated", "version bumped in three files"): verify by reading/grepping the relevant files.
- **Not actionable by an agent** (e.g. "repository secret configured in GitHub"): **skip it** and record it for the final report so it doesn't block the rest — flag it clearly as needing a human.

For any runnable/inspectable item that is **not satisfied**, dispatch a `phase-developer` to fix exactly that item (brief: the failing item + the smallest relevant slice of plan context), re-verify the item yourself, and commit the fix (`Final checklist: <item>`). Reuse the developer↔verifier loop and the same 3-round bound if a fix is non-trivial.

## Step 4 — Final report to the user

Summarize:

- Phases completed and the commit for each.
- Final Checklist: each item's status — passed / fixed+committed / **skipped — needs human** (with the reason).
- Any escalations or items left open.
- The branch name, reminding the user that nothing was pushed — review and push/PR is theirs.
