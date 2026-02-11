---
name: plan-export
description: Export a detailed phased implementation plan for a GitHub issue to a file, reading all applicable rules from .cursor/rules before planning
argument-hint: [issue-number (optional)]
disable-model-invocation: true
hooks:
  PreToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/allow-temp-writes.py"
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/allow-temp-dirs.py"
---

# Plan Export Skill

This skill composes a detailed, phased implementation plan for a GitHub issue. The issue number can be passed as `$1` or discovered from the conversation context (e.g., after a `/gh-issue-publish` invocation). The plan is designed for a junior developer with minimal knowledge of MCP, Blockscout, and other 3rd-party components but strong Python experience.

## Prerequisites

Before invoking this skill, the agent must already understand the scope of the changes through prior conversation. The skill assumes:

1. The feature/issue has been thoroughly discussed
2. The agent understands what needs to be changed
3. The agent has read the relevant source files that will be modified

## Workflow

### 0. Determine Issue Number

Before proceeding, resolve the GitHub issue number to use throughout the plan:

1. **If `$1` is provided and non-empty**, use it directly as the issue number.
2. **Otherwise**, search the current conversation for:
   - A GitHub issue URL matching `https://github.com/.../issues/<number>` — extract the number from the URL. This is typically present after a preceding `/gh-issue-publish` invocation (which outputs the URL).
   - An explicit issue number reference like `#<number>` or `issue <number>`.
3. **If multiple distinct issue numbers are found** in the conversation, list them and ask the user which one to use.
4. **If no issue number can be determined** from either source, ask the user to provide one before continuing.

Once resolved, use this number as `$1` for all subsequent steps.

### 1. Identify Applicable Guidelines

Read `.cursor/AGENTS.md` to determine which rules from `.cursor/rules/` apply to the discussed changes. That file contains the authoritative mapping of when each rule should be applied.

### 2. Read All Applicable Rules

**MANDATORY:** Read each applicable rule file using the Read tool before composing the plan. Do not skip this step or guess rule contents.

For each rule file:

1. Read the complete file content
2. Note specific requirements, patterns, and constraints
3. Incorporate these into the implementation plan

### 3. Compose the Implementation Plan

Create a detailed Markdown document at `temp/impl_plans/issue-$1.md` with the following structure:

```markdown
# Implementation Plan for Issue #$1

**GitHub Issue:** https://github.com/blockscout/mcp-server/issues/$1

## Overview

[Brief summary of what needs to be implemented - 2-3 sentences]

## Applicable Guidelines

[List the rule files that were read and applied to this plan, with brief notes on key requirements from each]

---

## Phase 1: [Phase Name - Functional Changes]

### Objective

[What this phase accomplishes]

### Files to Modify/Create

- `path/to/file.py`: [Brief description of changes]
- ...

### Implementation Details

[Explain WHAT needs to be changed and WHY. Focus on project-specific context the developer needs to understand:]

- What existing patterns/helpers to reuse and where to find them
- What project conventions apply (naming, structure, error handling approach)
- How this change fits into the existing architecture
- Any non-obvious dependencies or side effects

**Do NOT include code snippets.** The developer knows Python - explain the project-specific aspects they need to understand.

### Unit Tests

- **File:** `tests/tools/category/test_feature.py`
- **Purpose:** [What functionality this test validates]
- **Scenarios to cover:**
  - [List scenarios: success cases, error handling, edge cases]
- **Reference:** [Point to similar existing test file as a pattern example]

### Verification

1. Run unit tests for modified functionality:

   ```bash
   pytest tests/tools/category/test_feature.py -v
   ```

2. Run linting and formatting checks:

   ```bash
   ruff check path/to/modified/files/
   ruff format --check path/to/modified/files/
   ```

3. Fix any linting or formatting issues before proceeding to the next phase.

---

## Phase 2: [Phase Name - Additional Functional Changes]

[Same structure as Phase 1, including its own unit tests]

---

## Phase N-1: Integration Tests

### Objective

Verify the implementation works correctly with real network calls.

### Files to Create

- `tests/integration/category/test_feature_real.py`

### Test Scenarios

- **Purpose:** [What real-world functionality this validates]
- **Scenarios to cover:** [List scenarios with expected outcomes]
- **Reference:** [Point to similar existing integration test as a pattern example]

### Verification

1. Run integration tests for the new test file:

   ```bash
   pytest -m integration tests/integration/category/test_feature_real.py -v
   ```

2. Run linting and formatting checks:

   ```bash
   ruff check tests/integration/category/test_feature_real.py
   ruff format --check tests/integration/category/test_feature_real.py
   ```

3. Fix any linting or formatting issues before proceeding to the next phase.

---

## Phase N: Documentation Updates (if needed)

**Only include this phase if documentation changes are required.** If no documentation updates are needed, omit this phase entirely.

### Documentation Files

For each documentation file that requires changes, provide **exact text content** to add or modify (documentation requires precise wording):

#### SPEC.md

[Exact section and content to add/modify, if applicable]

#### AGENTS.md

[Exact section and content to add/modify, if applicable]

#### API.md

[Exact section and content to add/modify, if applicable]

#### README.md

[Exact section and content to add/modify, if applicable]

#### TESTING.md

[Exact section and content to add/modify, if applicable]

#### .env.example

[Exact lines to add, if applicable]

### Verification

Review all documentation files for accuracy and completeness.

---

## Final Checklist

- [ ] All phases completed and verified (including per-phase linting)
- [ ] All unit tests pass: `pytest tests/tools/`
- [ ] All integration tests pass: `pytest -m integration tests/integration/`
- [ ] Final linting check on entire codebase: `ruff check .`
- [ ] Final formatting check on entire codebase: `ruff format --check .`
- [ ] Documentation updated (if applicable)
- [ ] Version bumped (if applicable)

```

### 4. Content Guidelines

**MUST INCLUDE:**

- Reference to the GitHub issue (with full URL)
- List of applicable guidelines that were read and applied
- Phases that allow incremental verification
- Explanations of WHAT to change and WHY (project-specific context)
- References to existing code as pattern examples (file paths, not snippets)
- Complete documentation text (documentation requires precise wording)
- Specific test scenarios with clear descriptions
- Verification steps for each phase (including tests, linting, and formatting checks)

**MUST NOT INCLUDE:**

- Code snippets for functional changes or tests (developer knows Python)
- Time estimates
- Assumptions about developer's MCP/Blockscout knowledge
- References to "see documentation" without providing the content
- Vague instructions like "update as appropriate"

**PHASE ORGANIZATION:**

1. Only include phases that have actual work to do - omit empty phases
2. **Keep phases small and focused**: Each phase should have a single, clear objective that can be completed, tested, and reviewed as an independent unit. Prefer multiple small phases over fewer large ones.
3. Organize phases so each can be independently verified with its own tests
4. Start with core functionality, then tests, then documentation (if needed)
5. Each phase should build on the previous one

**Phase Size Rationale**: Since each phase's code goes through review, smaller phases are easier to review thoroughly. Catching issues early (e.g., in a model definition phase) prevents building faulty logic on top of flawed foundations.

**Examples of Good Phase Breakdown**:
- ❌ **Too Large**: Phase 1: Create model + handler + all unit tests
- ✅ **Better**: Phase 1: Create model + model unit tests, Phase 2: Create handler + handler unit tests
- ❌ **Too Large**: Phase 1: Refactor 5 modules + add new feature + update tests
- ✅ **Better**: Phase 1: Refactor module A + tests, Phase 2: Refactor module B + tests, Phase 3: Add new feature + tests

**DEPENDENCY ORDERING:**

1. **Between Phases**: Changes in a subsequent phase must build on top of changes from previous phases. Never reference functionality that will be created in a later phase.
2. **Within a Phase**: In the "Implementation Details" section, describe dependencies before things that use them:
   - If a handler uses a data model, describe the model first, then the handler
   - If code imports a helper function, describe the helper first, then the code using it
   - If a test requires a fixture, describe the fixture first, then the test
3. **Files Listing Order**: In "Files to Create/Modify" sections, list files in dependency order (dependencies first)

### 5. Write the Plan File

Save the plan to:

```text
temp/impl_plans/issue-$1.md
```

### 6. Output and Control Transfer

After writing the plan file:

1. Confirm the file was created with the full path
2. Provide a brief summary of the phases
3. **Stop and wait for user instructions** - do NOT begin implementing the plan

Output format:

```text
Created implementation plan at [temp/impl_plans/issue-$1.md](temp/impl_plans/issue-$1.md)

The plan includes {N} phases:
1. [Phase 1 name]
2. [Phase 2 name]
...

Applicable guidelines that were incorporated:
- [List of rule files read]

Awaiting your instructions to proceed.
```

## Important Notes

- **Do NOT implement the plan** - only create the plan document
- The plan must be self-contained and not assume access to conversation history
- **Only include phases with actual work** - do not create placeholder phases that say "no changes needed"
- **No code snippets** for functional changes or tests - explain WHAT and WHY instead
- Point to existing files as pattern examples (e.g., "follow the pattern in `tools/address/get_address_info.py`")
- Documentation updates DO require exact text content (prose requires precise wording)
- If the conversation lacks sufficient context, ask clarifying questions before creating the plan
- Each phase must have clear verification criteria so the developer knows when it's complete
- Each phase's verification must include linting and formatting checks for code-quality assurance before proceeding
