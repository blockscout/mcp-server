---
name: implementation-plan-review
description: Expert review of an implementation plan against a GitHub issue/enhancement description (provided as a local file or a GitHub issue URL) and the current repository codebase. Use when asked to critique a plan for correctness, completeness, codebase alignment, risks, and test/rollout readiness (do not implement).
disable-model-invocation: true
---

# Implementation Plan Review (Expert)

Review an implementation plan for coverage, correctness, and fit with the current codebase. Do not implement.

## Inputs

- Implementation plan: a local file path.
- Issue/requirements: either (a) a local file path, or (b) a GitHub issue number (run from the target repo so `gh` resolves it).

If the user provides a GitHub issue number, prefer fetching it into a local file using the bundled script (requires `gh` auth and network access; otherwise ask for a local issue description file):

```bash
bash scripts/fetch_github_issue.sh <issue-number> --out /tmp/issue.md
```

Run this command from the skill directory when that directory is inside the target repository. If it is not, keep the
command agent-agnostic by resolving the script path relative to this skill directory while running `gh` from the target
repo so the issue number resolves against the correct repository.

If the script reports that `gh` is not authenticated (exit code `3`), ask the user to run:

```bash
gh auth login
```

## Workflow

1) Prepare clean scratchpads:
   - Before reading or listing any scratchpad files, run from this skill directory:

```bash
bash scripts/prepare_scratchpads.sh <plan-file>
```

   - Use the printed `OK <scratchpad-path>` directory for all scratchpads in this review.
   - Existing scratchpads are stale working artifacts; never read or preserve them for a new review.
   - If the script reports `ERROR`, stop and report the failure.

2) Read the two inputs in full:
   - Plan file
   - Issue description file (or the fetched `/tmp/issue.md`)

3) Apply versioning neutrality policy:
   - Do **not** request a missing version bump (package version, `server.json`, manifests, etc.) unless a repo rule, user instruction, release plan, or issue text explicitly requires one.
   - Do **not** suggest removing version bump steps merely because the issue does not mention versioning. Issues usually describe the problem, motivation, or code-level improvement; they are not expected to spell out release mechanics.
   - If the plan already includes version bump steps, review them only for correctness and consistency with applicable repo rules: required files, matching version strings, valid version format, and no unrelated version/manifests changed.
   - Raise a versioning finding only when the plan's versioning steps are internally inconsistent, contradict explicit requirements, or are objectively attached to the wrong files/surfaces.

4) Apply review-noise policy:
   - Do not raise findings only because an implementation plan omits developer execution mechanics such as checking `/.dockerenv`, choosing host vs devcontainer command prefixes, or spelling out both command variants.
   - Do not teach command invocation mechanics in recommendations.
   - Review verification semantically: required test/lint/integration categories, targets, and coverage, not how a developer invokes commands in their environment.
   - Still flag objectively wrong verification scope, such as requiring only a narrow test subset when repo rules require the full default suite.

5) Validate codebase reality (start targeted, expand as needed):
   - Start by finding referenced modules/configs/env vars/tests with `rg` (fast and low-noise).
   - Prefer opening the minimal set of files *first* to confirm patterns and naming, but broaden freely if you suspect hidden coupling or cross-cutting behavior (e.g., shared helpers, config loading, response models, pagination, truncation).
   - If the plan touches MCP tools, REST API, docs, or tests, cross-check relevant `.cursor/rules/*.mdc` guidance.
   - If it improves confidence, use any other repo investigation strategy (e.g., inspect docs like `SPEC.md`/`API.md`, check tests, use `git blame`, or run unit tests/lint locally).

Suggested commands (adapt as needed):

```bash
rg -n "name_in_plan|function_in_plan|ENV_VAR_IN_PLAN" -S .
rg -n "ToolResponse\\[|@mcp\\.tool\\(|log_tool_invocation" blockscout_mcp_server -S
rg -n "ServerConfig\\(|BaseSettings\\(|BLOCKSCOUT_" blockscout_mcp_server/config.py -S
rg -n "pytest\\.mark\\.integration|tests/integration|tests/tools" tests -S
```

6) Ground findings with scratchpads:
   - Use only the clean scratchpad directory prepared in step 1.
   - For each actionable candidate finding, create one deterministic scratchpad file in final report order:
     - `finding-01-short-slug.md`
     - `finding-02-short-slug.md`
     - Continue numbering in the same order used in §4.
   - Each scratchpad must include these sections:
     - `Grounded context`: exact code, docs, tests, configs, or rules inspected, with paths/functions/classes where relevant.
     - `Variants`: at least 2 meaningful solution options; use 3-4 for non-trivial findings.
     - `Rubric`: criteria for choosing between variants.
     - `Evaluation`: a score table or concise comparison of variants against the rubric.
     - `Best recommendation`: the concrete change to make to the implementation plan.
     - `Plain-language rationale`: why the chosen recommendation is best.
   - Use the scratchpad result to rewrite the final §4 recommendation. If scratchpad investigation disproves or weakens a finding, remove it or downgrade it before final output.
   - Findings that cannot be grounded in a scratchpad should normally be omitted. Keep them only when they are genuinely product/intent questions and mark them as `Question`.

Scratchpad discipline:
- Scratchpads are working artifacts created by this review skill to make final recommendations grounded.
- Do not create scratchpads for pure summary text, obvious nits, or questions that require user/product input rather than code investigation.
- Do not use scratchpads to pad the report; use them only to make actionable recommendations more accurate.

7) Produce the review in the required format (next section).

## Required output format

Produce a review with these sections:

### 1) Understanding

- Issue summary
- Acceptance criteria (bulleted)

### 2) Plan ↔ Requirements coverage

- What is covered well
- What is missing / ambiguous

### 3) Codebase alignment

- Key files/modules you inspected (with paths)
- Assumptions in the plan that match the codebase
- Assumptions that don’t match (explain and suggest correction)

### 4) Review comments (actionable)

Provide comments as a list. Each comment must include:

- Severity: `Blocker | Major | Minor | Question | Nit`
- Location: plan section/step + (when relevant) repo file/function/class
- Problem: what’s wrong / missing
- Recommendation: concrete change to the plan
- Rationale: why it matters (bug risk / security / perf / maintainability)
- Scratchpad: path to the backing scratchpad file, when the comment is actionable and not a pure `Question`

**Testing gaps rule:**

- List every specific missing/incorrect test as an actionable comment in **§4**.
- In **§6**, provide a consolidated checklist that references those items **without repeating full explanations**.

### 5) Junior-dev readiness check

- Missing task-specific prerequisites, step ordering, and verification coverage
- Do not flag omitted environment-specific command invocation details
- Where the plan needs more explicit detail

### 6) Test & rollout strategy

- Consolidated test checklist (Unit / Integration / E2E / Negative & security / Performance & regression), referencing §4 test comments
- Migration/rollback plan if applicable
- Feature flags / safe rollout suggestions if applicable

## Review focus checklist (use as prompts, not new requirements)

- Coverage: every acceptance criterion mapped to plan steps.
- Codebase alignment: paths, module structure, naming, existing helpers and patterns.
- Edge cases & compatibility: pagination, timeouts, empty results, truncation limits, backward compatibility.
- Security: input validation, SSRF/DNS rebinding boundaries, secrets handling, logging redaction, auth assumptions.
- Performance/scale: API call counts, caching, pagination strategy, long-running tasks/progress updates.
- Ops/observability: error handling, logs, metrics/telemetry/analytics implications, rollout/rollback.
- Versioning: only comment if explicitly required by the issue description; otherwise assume omission is intentional.
