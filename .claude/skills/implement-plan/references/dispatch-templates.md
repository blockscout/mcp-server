# Dispatch templates

Exact text to pass each subagent. The plan has already been sliced into per-section files by `scripts/slice_impl_plan.py` (skill Step 1); you pass **paths**, never pasted content. Fill the `<...>` placeholders with the real slice directory, phase number, title, baseline SHA, and (on a gap round) the verifier's gap list. The slice files are the verbatim source of truth; your only job is to route paths. The subagents' output formats live in their own agent files (`.claude/agents/`), not here.

`SLICE_DIR` below is the `.ai/tmp/impl/<plan-stem>/` directory reported in the slicer's manifest.

## Brief for `phase-developer` — first round

```
You are implementing ONE phase of an implementation plan. Implement only this phase.

Read these files first — they are the verbatim plan text and your source of truth:
- PLAN PREAMBLE (binds every phase: Overview, Applicable Guidelines, Definition of Done — Test Integrity, any Ordering/Environment notes): <SLICE_DIR>/preamble.md
- YOUR TARGET PHASE (your only deliverable): <SLICE_DIR>/phase-<N>.md

OTHER PHASES (titles only, for resolving cross-references like "removed in Phase 5"):
<one line per other phase: "Phase K: <title>">

BASELINE: phases before this one are already implemented and committed on the current branch; the working tree reflects them. Build on top. Do NOT commit — the orchestrator commits after verification.
```

## Brief for `phase-developer` — gap round

Same as the first-round brief, with this appended:

```
VERIFIER GAP REPORT (close exactly these):
<the verifier's GAPS_FOUND list, verbatim>

Your prior work from the previous round is already in the working tree. Do not start over — address exactly the gaps above, then re-run the relevant checks.
```

## Brief for `plan-correspondence-verifier`

```
Verify that ONE phase was implemented completely and honestly. You are a correspondence checker, not a code reviewer.

Read these files first — they are the verbatim plan text:
- PLAN PREAMBLE (how to run tools in this repo, and the Definition of Done — Test Integrity, which is your honesty charter): <SLICE_DIR>/preamble.md
- PHASE UNDER VERIFICATION: <SLICE_DIR>/phase-<N>.md

BASELINE REF: judge only the changes between <baseline commit SHA — captured with `git rev-parse HEAD` before the first developer of this phase> and the current working tree. The phase's work is **uncommitted**: inspect it with `git diff <baseline>` (no `..`) plus `git status --porcelain` for new/untracked files. Do not use `git diff <baseline>..` — that compares two commits and shows nothing while the work is uncommitted.

Build your own checklist from the phase text, inspect the actual diff and files (not the developer's claims), re-run the cheap deterministic checks yourself, verify integration-test evidence without re-running it (unless this brief includes the integration-re-run block below), and return your VERDICT in the structure your instructions define.
```

## Optional add-on for `plan-correspondence-verifier` — integration-deliverable phases only

Append this block to the verifier brief **only** when the phase's actual deliverable *is* an integration test (a live test plus its skip-gate). Omit it for every other phase.

```
== INTEGRATION RE-RUN (authorized for this phase) ==
NOTE ON INTEGRATION EVIDENCE: this phase's deliverable is a live integration test and its skip-gate, so confirming it first-hand matters. You MAY re-run THIS phase's targeted integration through the timeout runner — `python scripts/run_integration_tests.py <only this phase's integration test files>` — to verify the test actually ran (or skipped for the right reason) rather than taking the developer's word. Re-run only those targeted files, never the whole suite; the full authoritative run happens at the Final Checklist.
```

## Notes

- The plan slices live under `.ai/tmp/impl/<plan-stem>/` (gitignored): `preamble.md`, `phase-1.md` … `phase-N.md`, `final-checklist.md`. Pass paths, never paste the content.
- The phase titles for cross-references come from the slicer's manifest (its `title=` per slug).
- The **baseline ref** for the verifier is the SHA captured with `git rev-parse HEAD` *right before* dispatching the first developer for that phase — not after.
- Both subagents read the **same** `preamble.md`; it carries the environment rule and the Definition of Done.
- For a **Final Checklist fix**, brief the developer with the failing checklist item plus the path to the most relevant slice (often the phase that item came from), and the instruction to fix only that item.
- Add the **INTEGRATION RE-RUN** block to the verifier's brief *only* for a phase whose deliverable is itself an integration test (a live test + its skip-gate). For all other phases omit it — the verifier defaults to evidence-only, and the full suite gets its one authoritative run at the Final Checklist.
- If the plan had no markers and you fell back to slicing by headings yourself (skill Step 1, exit code 2), write the same filenames into the same `.ai/tmp/impl/<plan-stem>/` directory so these briefs work unchanged.
```
