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

## One rule above all: pass slices by reference, never paraphrase

The plan is cut into per-section files by `scripts/slice_impl_plan.py` (Step 1). You hand each subagent the **path** to the slice it needs — you never paste the content into a prompt, and you never summarize or reword it. Pasting copies the same bytes into your context once per phase and once per round, driving you toward compaction; paraphrasing can silently drop a step, and then *both* the developer (who won't build it) and the verifier (who won't check it) inherit the loss. The slice files on disk are the single verbatim source of truth. Your job is to route paths, capture baselines, and commit.

## The two subagents

- **`phase-developer`** (model: sonnet, full tooling) — reads its phase slice by path and implements that one phase. Defined in `.claude/agents/phase-developer.md`.
- **`plan-correspondence-verifier`** (model: opus, read-only) — reads the same phase slice and checks that every step was actually done, honestly. It inspects the real diff and re-runs cheap checks; it is *not* a code reviewer. Defined in `.claude/agents/plan-correspondence-verifier.md`.

Both subagents return **lean** reports by design: the developer restates only its integration-test evidence and any blocker — you and the verifier reconstruct everything else from the real diff — and the verifier returns a single-line `Checked` summary on success. Full evidence stays in each subagent's own transcript; keeping it out of *your* context is what keeps the run small and traceable. When you relay the developer's integration evidence to the verifier, pass it **verbatim** — same rule as the slices: never summarize a subagent's output before handing it on.

The exact text to pass each one is in [references/dispatch-templates.md](references/dispatch-templates.md). Read it before dispatching.

## Step 0 — Preconditions

1. Confirm the plan file exists at the path in `$ARGUMENTS`. If the path wasn't provided, ask which plan to implement. Do **not** read the whole plan into your context — Step 1 slices it into files and you dispatch by path; keeping the full plan out of your own context is the point of this design.
2. Check the current branch (`git branch --show-current`). If it is `main` (the default branch), **stop** and ask the user to create and check out a working branch first — this skill commits as it goes and must not commit onto `main`.
3. Check the working tree (`git status`). If there are unrelated uncommitted changes, surface them and confirm with the user before proceeding, so per-phase commits stay clean. (The plan slices are written under `.ai/tmp/impl/`, which is gitignored, so they never enter your commits.)

## Step 1 — Slice the plan into per-section files

Run the slicer; it validates the plan's markers and writes one file per section. Follow the repo's environment rule (devcontainer — `/.dockerenv` exists: run `python …`; host: `uv run python …`):

```bash
python scripts/slice_impl_plan.py <plan-file>
```

It writes `.ai/tmp/impl/<plan-stem>/` with `preamble.md`, `phase-1.md` … `phase-N.md`, and `final-checklist.md`, and prints a manifest (each slug, its file path, and its phase `title`). **Branch on the exit code:**

- **0** — slices written. Read the manifest from stdout for the slug → title map and the file paths. Dispatch subagents by **path** (each region's file is `<out-dir>/<slug>.md`); never paste the content.
- **2** — the plan has no slice markers (a legacy plan, produced before `plan-export` emitted them). Fall back: slice it yourself, mechanically, by headings — preamble = everything before `## Phase 1`; each `## Phase N:` block; the `## Final Checklist` — and write those slices into `.ai/tmp/impl/<plan-stem>/` under the **same filenames**, so the rest of the run is identical. If embedded docs or code make heading-slicing ambiguous, stop and ask the user.
- **1** — markers are present but malformed; the slicer printed exactly what is wrong (unbalanced, duplicated, out of order, or content outside a region). **Stop and report it — do not guess.** The plan must be fixed first (re-run `plan-export`, or fix the markers and re-validate with `--inspect`).

Capture the slug → title list and the slice directory; Step 2 dispatches from these files.

## Step 2 — Implement each phase, in order

Phases are sequential; never start phase N+1 before phase N is committed (the plan's ordering often depends on it). For each phase:

1. **Record the baseline**: `git rev-parse HEAD` — the ref the verifier diffs against for this phase. Capture it *before* dispatching the developer.
2. **Dispatch a fresh `phase-developer`** with the first-round brief from the templates file: the **paths** to `preamble.md` and this phase's `phase-<N>.md`, the other-phase titles (from the manifest), and the baseline note. Its report is deliberately short — a status line, its integration-test evidence (or "none"), and anything it could not complete. Note the integration-evidence block to relay next; a "could not complete" means escalate (step 5).
3. **Dispatch a fresh `plan-correspondence-verifier`** with its brief: the **paths** to `preamble.md` and this phase's `phase-<N>.md`, the baseline ref, and the developer's integration-evidence block lifted **verbatim** (or "none"). Read its verdict — on `COMPLETE` it is just two lines; the per-step detail stays in the verifier's own transcript, not your context. If this phase's deliverable *is* an integration test (a live test plus its skip-gate), also append the optional **integration-re-run** block from the templates so the verifier can confirm first-hand that the test ran rather than silently skipped.
4. **Branch on the verdict:**
   - `COMPLETE` → go to step 5.
   - `GAPS_FOUND` → dispatch a **fresh** `phase-developer` with the gap-round brief: the same context plus the verifier's gap list verbatim and "your prior work is already in the working tree; close exactly these gaps." Then go back to step 3 to re-verify.
5. **Bound the loop.** Allow at most **3** developer↔verifier rounds for a phase. If the verifier still reports gaps after the 3rd round — or if a developer reports it *cannot* complete a step — **stop and escalate to the user**: show the latest developer report and the verifier's outstanding gaps, and ask how to proceed. Never commit an unverified phase.
6. **Commit the phase** on the current branch once the verdict is `COMPLETE`. Use a message like `Phase <N>: <phase title>`. Do **not** push and do **not** open a PR — leave the branch for the user to review. End the commit message with the harness `Co-Authored-By` trailer.
7. For the final summary you need only the phase's title, its commit, and any "could not complete"/escalation — not verbose prose. The trimmed developer and verifier reports already give you exactly that; detailed evidence stays in each subagent's transcript.

Each phase = one commit. A fresh developer every round is intentional: all state lives in the git working tree, so a new subagent loses nothing and stays focused on exactly the open gaps.

## Step 3 — Final Checklist

After all phases are committed, read the Final Checklist slice (`<slice-dir>/final-checklist.md`) and walk each item. Classify each:

- **Runnable check** (essentially a command — `grep`, `pytest`, `ruff check`, `ruff format --check`, or a full integration run via `python scripts/run_integration_tests.py tests/integration/`): run it yourself and read the result. This is where the **full integration suite gets its one authoritative independent run.**
- **Inspectable claim** (e.g. "documentation updated", "version bumped in three files"): verify by reading/grepping the relevant files.
- **Not actionable by an agent** (e.g. "repository secret configured in GitHub"): **skip it** and record it for the final report so it doesn't block the rest — flag it clearly as needing a human.

For any runnable/inspectable item that is **not satisfied**, dispatch a `phase-developer` to fix exactly that item (brief: the failing item + the path to the most relevant slice). Because **you re-run the defining check yourself**, the fix developer need only report "done" or "blocked, because …" — don't rely on a verification narrative. Re-verify the item yourself, then commit the fix (`Final checklist: <item>`). Reuse the developer↔verifier loop and the same 3-round bound if a fix is non-trivial.

## Step 4 — Final report to the user

Summarize:

- Phases completed and the commit for each.
- Final Checklist: each item's status — passed / fixed+committed / **skipped — needs human** (with the reason).
- Any escalations or items left open.
- The branch name, reminding the user that nothing was pushed — review and push/PR is theirs.
