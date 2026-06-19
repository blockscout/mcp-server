---
name: review-plan-findings-feedback
description: Manually review a feedback file produced after implementation-plan review findings were addressed. Use when the user asks to read a findings-feedback file and verify that the plan changes correctly close, correctly reject, or fail to close the original implementation-plan-review findings, while checking for newly introduced or newly exposed plan problems. Writes only new findings to the plan-id findings directory and replies with the output file path or a concise no-new-findings status.
disable-model-invocation: true
---

# Review Plan Findings Feedback

Review a follow-up feedback file after plan-review findings were addressed. Do not implement code and do not edit the plan. The only possible artifact is a new-findings file.

## Inputs And Assumptions

- The user provides the feedback file path, usually `.ai/impl_plans/<plan-id>-findings-feedback/feedback.md`.
- The implementation plan path and the original review findings are expected to already be present in the conversation context because this skill is run in the same session as `implementation-plan-review`.
- Do not require the user to pass the plan path or original findings again. Infer the plan id from the current session first, then from the feedback path if needed.
- If the plan id or original findings cannot be recovered with confidence, stop and ask for the missing context rather than guessing.

## Workflow

### 1. Resolve The Plan Id

Infer exactly one `plan-id`, such as `issue-418`.

Priority:

1. The most recent implementation plan path in session context: `.ai/impl_plans/<plan-id>.md`.
2. The feedback file path: `.ai/impl_plans/<plan-id>-findings-feedback/feedback.md`.
3. Scratchpad paths from the prior review: `.ai/impl_plans/<plan-id>-scratchpads/...`.

Confirm `.ai/impl_plans/<plan-id>.md` exists before proceeding.

### 2. Reset The New-Findings Directory First

Before reading or listing any files under `.ai/impl_plans/<plan-id>-findings/`, run:

```bash
bash .agents/skills/review-plan-findings-feedback/scripts/reset_findings_dir.sh <plan-id>
```

Use the printed absolute directory path for this run's output. If the script exits non-zero, fix the cause and rerun it before doing review work.

### 3. Read Required Inputs

Read in full:

- The feedback file supplied by the user.
- The current implementation plan: `.ai/impl_plans/<plan-id>.md`.
- The original review findings from the current conversation context.

Read targeted evidence as needed:

- Prior scratchpads cited by the original findings.
- Relevant code, tests, docs, and `.cursor/rules/*.mdc` files needed to verify whether the feedback and plan edits are correct.

Do not open unrelated implementation plans.

### 4. Re-Review The Closure

For each original finding:

- Check whether the feedback accurately understood the finding.
- Check whether the current plan actually changed in a way that closes the valid part of the finding.
- If the feedback rejects the finding, decide whether the rejection is acceptable. Treat an accepted rejection the same as a closed finding: do not report it as new/unresolved.
- Re-check the underlying code/rules when the finding depends on codebase reality.

Then scan the edited plan sections for newly introduced or newly exposed issues. Apply the same review standard as `implementation-plan-review`, but only report findings that are new after the feedback round or still unresolved despite the feedback.

Do not report:

- Findings that are fully closed.
- Pure summaries.
- Style nits that do not affect correctness, coverage, maintainability, safety, or junior-dev readiness.
- Environment command-prefix mechanics, unless the verification scope itself is objectively wrong.

### 5. Write Output Only If New Findings Exist

If new findings exist, create exactly one Markdown file:

```text
.ai/impl_plans/<plan-id>-findings/findings.md
```

The file must contain only a list of new findings. Do not add an introduction, summary, "no findings" line, or review sections.

Use this item shape:

```markdown
- **Severity:** Major
  **Location:** Phase N / plan section + relevant repo file or rule
  **Problem:** What remains wrong or what new problem was introduced.
  **Recommendation:** Concrete change to the plan.
  **Rationale:** Why it matters.
```

If there are no new findings, do not create any file in the findings directory.

### 6. Chat Output

If a findings file was created, reply with only a clickable link to it:

```markdown
[.ai/impl_plans/<plan-id>-findings/findings.md](.ai/impl_plans/<plan-id>-findings/findings.md)
```

If no new findings were found and every original finding was closed by plan edits, reply exactly:

```text
No new findings.
```

If no new findings were found and at least one original finding was rejected by the feedback but you accept the rejection, reply exactly:

```text
No new findings. Rejections accepted.
```

Do not repeat findings in chat.
