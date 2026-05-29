# Dispatch templates

Exact text to pass each subagent. Fill the `<...>` placeholders with **verbatim** plan slices — never paraphrase. The orchestrator slices; these templates wrap the slices with just enough framing. The subagents' output formats live in their own agent files (`.claude/agents/`), not here.

## Brief for `phase-developer` — first round

```
You are implementing ONE phase of an implementation plan. Implement only this phase.

== PLAN PREAMBLE (binds every phase — read it) ==
<preamble verbatim: Overview, Applicable Guidelines, Definition of Done — Test Integrity, Ordering/Environment notes>

== OTHER PHASES (titles only, for resolving cross-references) ==
<one line per other phase: "Phase K: <title>">

== YOUR TARGET PHASE (your only deliverable) ==
<Phase N block, verbatim, all subsections>

== BASELINE ==
Phases before this one are already implemented and committed on the current branch; the working tree reflects them. Build on top. Do not commit — the orchestrator commits after verification.
```

## Brief for `phase-developer` — gap round

Same as the first-round brief, with this appended:

```
== VERIFIER GAP REPORT (close exactly these) ==
<the verifier's GAPS_FOUND list, verbatim>

Your prior work from the previous round is already in the working tree. Do not start over — address exactly the gaps above, then re-run the relevant checks.
```

## Brief for `plan-correspondence-verifier`

```
Verify that ONE phase was implemented completely and honestly. You are a correspondence checker, not a code reviewer.

== PLAN PREAMBLE (includes how to run tools in this repo, and the Definition of Done — Test Integrity, which is your honesty charter) ==
<preamble verbatim>

== PHASE UNDER VERIFICATION ==
<Phase N block, verbatim, all subsections>

== BASELINE REF ==
Judge only the changes between <baseline commit SHA — captured with `git rev-parse HEAD` before the first developer of this phase> and the current working tree.

Build your own checklist from the phase text, inspect the actual diff and files (not the developer's claims), re-run the cheap deterministic checks yourself, verify integration-test evidence without re-running it, and return your VERDICT in the structure your instructions define.
```

## Notes

- The **baseline ref** for the verifier is the SHA captured with `git rev-parse HEAD` *right before* dispatching the first developer for that phase — not after.
- Pass the **same** preamble to both subagents; it carries the environment rule and the Definition of Done.
- For a **Final Checklist fix**, brief the developer with the failing checklist item plus the smallest relevant slice of plan context (often the phase that item came from), and the instruction to fix only that item.
