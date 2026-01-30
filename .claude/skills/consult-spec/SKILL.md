---
name: consult-spec
description: |
  TRIGGER CONDITIONS - invoke this skill when ANY of these apply:

  User-triggered (explicit request):
  - User mentions "specification", "SPEC", "SPEC.md", "spec requirements"
  - User asks to "verify with spec", "confirm with specification", "check requirements"
  - User requests "authoritative requirements" or "source of truth"

  Agent self-triggered (during reasoning):
  - Before implementing any feature or making code changes
  - When verifying technical requirements or constraints
  - When making architectural or design decisions
  - When you need unbiased guidance not influenced by current implementation
  - When encountering conflicting information and need ground truth

  PURPOSE: Consults SPEC.md through an isolated subagent that ONLY reads the
  specification, never implementation code. This ensures guidance is based on
  authoritative requirements, not potentially incorrect existing code.
user-invocable: false
---

# SPEC.md Consultation Skill

Before implementing any feature or making architectural decisions, consult SPEC.md through an isolated Explore agent to understand the authoritative requirements and design principles.

## Purpose

This skill provides access to SPEC.md (the source of truth for architecture and requirements) through a dedicated subagent that ONLY reads the specification, never the implementation code. This ensures you receive unbiased, authoritative guidance based on requirements rather than potentially incorrect implementations.

## When to Use This Skill

**Use this proactively when you:**

- Begin implementing any feature (check spec requirements first)
- Design API responses or data structures (verify against spec models)
- Make architectural decisions (consult spec design principles)
- Need to understand design rationale for existing patterns
- Encounter conflicting information (get the ground truth)
- Verify technical requirements or constraints
- Check pagination strategies, error handling patterns, or data processing rules

**Do NOT use this when:**

- You need to understand current implementation details (read code directly)
- You need to see how something is actually implemented (that's not the spec's job)
- You're just checking a simple constant or configuration value

## Workflow

### 1. Formulate Your Question

Be specific about what you need from the spec:

**Good questions:**

- "What is the opaque cursor strategy for pagination?"
- "How should log data field truncation work?"
- "What are the design principles for response processing?"
- "What is the standardized ToolResponse model structure?"

**Bad questions:**

- "How is pagination implemented?" (this asks about code, not spec)
- "Tell me everything about transactions" (too broad)

### 2. Spawn the Spec Consultant Subagent

Use the Task tool to create an Explore agent with strict SPEC.md-only instructions:

```plaintext
Task tool parameters:
- subagent_type: "Explore"
- description: "Consult SPEC.md about <specific topic>"
- prompt: "You are a SPEC.md consultant. Your purpose is to provide authoritative
          requirements and design principles from the specification, NOT describe
          implementation details.

          CRITICAL CONSTRAINT: You may ONLY read SPEC.md from the current working directory.

          If asked about any other file, respond: 'I only consult SPEC.md. For
          implementation details, the main agent should read the code directly.'

          Workflow:
          1. Read SPEC.md (relative to current working directory)
          2. Analyze the content semantically to find relevant sections
          3. Provide a clear answer with line number references
          4. Quote key passages directly when helpful

          Note: Prefer reading the full file for semantic understanding rather than
          using grep, which may miss relevant sections due to terminology differences.
          The file is only 685 lines and well within your context capacity.

          Question: <your specific question>"
```

### 3. Resume for Follow-Up Questions

If you need multiple spec queries during the same implementation task:

- Capture the `agentId` from the first Task result
- Use `resume: <agentId>` parameter in subsequent Task calls
- This avoids re-reading SPEC.md and maintains context

### 4. Use the Answer in Your Work

The subagent will return:

- Specific information from SPEC.md
- Line number references (e.g., "lines 285-305")
- Direct quotes from relevant sections
- Design rationale and principles

Use this authoritative guidance to implement features correctly according to the specification.

## Example Usage

**Scenario**: Main agent is implementing a new feature that requires understanding spec requirements

**Main agent thinks**: "I need to understand the spec requirements before implementing this."

**Main agent invokes Task tool**:

```plaintext
subagent_type: "Explore"
description: "Consult SPEC.md about [topic]"
prompt: "You are a SPEC.md consultant. You may ONLY read SPEC.md from the current working directory.

Question: [Your specific question about requirements, architecture, or design principles]

Read the full file, analyze semantically, and provide line references with relevant quotes."
```

**Subagent responds** (abstract pattern):

```plaintext
The [requested concept/requirement] is defined in lines XXX-YYY of SPEC.md.

Key requirements:
- [First key principle or requirement from the spec]
- [Second key principle or requirement from the spec]
- [Third key principle or requirement from the spec]

Direct quote (lines XXX-YYY):
"[Relevant quote from the specification that clarifies the requirement]"

The [data structure/model/pattern] should contain:
- [component_name]: [description of requirement]
- [component_name]: [description of requirement]

Additional context in lines XXX-YYY explains [related concept].
```

**Main agent uses this**: Implements the feature correctly according to spec requirements

## Important Notes

### Subagent Scope Constraint

The Explore subagent is instructed to ONLY read SPEC.md. This is enforced through:

- Explicit instructions in the subagent prompt
- Clear rationale (provide source-of-truth, avoid implementation bias)
- Behavioral instruction to refuse other file requests

If the subagent attempts to read other files, strengthen the prompt wording or report the issue.

### Why This Matters

SPEC.md is the authoritative source of truth. Implementation code may contain:

- Bugs or deviations from requirements
- Incomplete features
- Temporary workarounds
- Outdated patterns

By consulting SPEC.md through an isolated subagent, you ensure your implementation decisions are based on requirements, not on potentially incorrect existing code.

### When to Read Code Directly

You still need to read implementation code when you're:

- Understanding existing patterns to match coding style
- Debugging specific issues
- Refactoring or modifying existing features
- Learning how a feature is currently implemented

Use SPEC.md consultation for "what should this do?" and code reading for "how is this currently done?"
