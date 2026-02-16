---
name: implementation-plan-review
description: Expert review of an implementation plan against a GitHub issue/enhancement description (provided as a local file or a GitHub issue URL) and the current repository codebase. Use when asked to critique a plan for correctness, completeness, codebase alignment, risks, and test/rollout readiness (do not implement).
---

# Implementation Plan Review (Expert)

Review an implementation plan for coverage, correctness, and fit with the current codebase. Do not implement.

## Inputs

- Implementation plan: a local file path.
- Issue/requirements: either (a) a local file path, or (b) a GitHub issue number (run from the target repo so `gh` resolves it).

If the user provides a GitHub issue number, prefer fetching it into a local file using the bundled script (requires `gh` auth and network access; otherwise ask for a local issue description file):

```bash
bash .codex/skills/implementation-plan-review/scripts/fetch_github_issue.sh <issue-number> --out /tmp/issue.md
```

If the script reports that `gh` is not authenticated (exit code `3`), ask the user to run:

```bash
gh auth login
```

## Workflow

1) Ensure repo startup constraints are satisfied:
   - In this repository, run `$codex-session-bootstrap` before doing any other work.

2) Read the two inputs in full:
   - Plan file
   - Issue description file (or the fetched `/tmp/issue.md`)

3) Apply strict versioning-comment policy:
   - Do **not** request or suggest any version bump (package version, `server.json`, etc.) unless the **issue description explicitly requires** a version bump/release/publish/tag.
   - Even if the plan changes externally-consumed surfaces (tool schemas, REST/OpenAPI, manifests), treat missing version bump steps as **intentional** unless the issue says otherwise.

4) Validate codebase reality (start targeted, expand as needed):
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

1) Produce the review in the required format (next section).

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

**Testing gaps rule:**

- List every specific missing/incorrect test as an actionable comment in **§4**.
- In **§6**, provide a consolidated checklist that references those items **without repeating full explanations**.

### 5) Junior-dev readiness check

- Missing prerequisites, commands, step ordering, “how to verify”
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
