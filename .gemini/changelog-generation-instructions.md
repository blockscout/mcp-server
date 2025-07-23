# Instructions for Generating the System Prompt Customization Changelog

**Objective:**

Your task is to perform a semantic comparison between two provided system prompt files: `system-prompt.md` (the original base prompt) and `system-prompt-new.md` (the project-specific, modified prompt). Based on this comparison, you will generate a new, well-structured Markdown document named `sp-customization-changelog.md`. This changelog must accurately and clearly document all changes, removals, and retentions, following the precise structure and format outlined below.

**Input Files:**

1. `system-prompt.md`: The original, generic system prompt.
2. `system-prompt-new.md`: The modified, project-specific system prompt.

**Output File:**

* `sp-customization-changelog.md`: A Markdown document detailing the transformation from the original to the new prompt.

---

### **Methodology & Step-by-Step Guide**

Follow this procedure meticulously.

**Step 1: Initial Analysis and Section Mapping**

1. Read the full content of both input files into memory.
2. Parse both documents to identify all top-level (`#`) and second-level (`##`) Markdown sections.
3. Create a map of all sections from the original prompt and compare it against the sections in the new prompt. This comparison will allow you to categorize every section from the original prompt into one of three states: **Retained**, **Removed**, or **Modified**.

**Step 2: Identify Removed Sections**

1. Identify any top-level (`#`) sections that exist in `system-prompt.md` but are completely absent from `system-prompt-new.md`.
2. These will be documented first in the changelog under the "Global Changes" section.
    * *Example*: You will find that the `# New Applications` section is present in the original but not the new prompt. This is a "Removed" section.

**Step 3: Identify Retained (Unchanged) Sections**

1. Identify all top-level (`#`) sections that are present in both documents and whose content is **100% identical**.
2. These will be documented in a dedicated "Retained Sections" part of the changelog to make it clear that they should be preserved as-is from the base prompt in any future updates.

**Step 4: Analyze Modified Sections in Detail**

1. For every section that exists in both documents but is **not** identical, perform a detailed, granular analysis to determine the nature of the change. Look for the following patterns:
    * **Complete Replacement:** The entire content of a section or a specific list item was replaced with new content.
        * *Example*: The `# Examples` section and the `Libraries/Frameworks` mandate under `# Core Mandates` were completely replaced.
    * **Content Appending:** New text was added to the end of an existing paragraph or list item.
        * *Example*: A new sentence was appended to the `Conventions` mandate.
    * **Content Prepending:** New text was added to the beginning of an existing paragraph or list item.
        * *Example*: New bolded text was added to the start of the `Understand` step in the workflow.
    * **Title Modification:** The heading text itself was changed.
        * *Example*: `# Primary Workflows` was changed to `# Primary Workflow: Software Engineering Tasks`.

**Step 5: Generate the Changelog Document**

Using the information gathered in the previous steps, construct the `sp-customization-changelog.md` file. Adhere strictly to the following structure and formatting rules.

---

### **Changelog Structure and Formatting Template**

```markdown
# System Prompt Customization Changelog for Blockscout MCP Server

This document outlines the specific modifications applied to the generic Gemini CLI system prompt to create a specialized version for the `blockscout-mcp-server` project. It is intended to be used by an AI agent to re-apply these customizations to future versions of the base prompt.

---

## 1.0 Global Changes

### 1.1 REMOVED: [Section Title]

<!-- For each section identified in Step 2, create a subsection like this. -->
The entire `#[Section Title]` workflow and its associated subsections have been removed.

- **Reasoning:** [Provide a brief, logical reason for the removal based on the context of the new prompt. For example: "The agent's role on this project is to maintain and enhance an *existing* codebase..."]

---

## 2.0 Retained Sections

<!-- List all identical top-level sections identified in Step 3 here. -->
The following top-level sections from the original `system-prompt.md` are to be retained in their entirety without modification. This ensures that future updates to the base prompt's core operational guidelines are automatically inherited.

- `#[Section Title 1]`
- `#[Section Title 2]`
- ...

---

## 3.0 Section-Specific Modifications

<!-- This section will contain the detailed analysis from Step 4. -->

### 3.X [Section Title]

<!-- For each modified section, create a subsection. Use a clear, descriptive title. -->

- **Original:** [Briefly describe the original state. e.g., "A generic instruction to mimic style."]
- **Modified:** [Briefly describe the new state. e.g., "Added specific details about the linter, formatter, and line length."]
- **Instruction:** [Provide a precise, actionable instruction for the change.]
    - For replacements, use: `Replace the entire [element] with:` followed by the new text in a quote block or code block.
    - For appends, use: `Append the following sentence to the end of the [element]:`
    - For prepends, use: `Add the following bolded text to the beginning of the step:`

<!-- For large content replacements like the Examples section, use this format: -->
### 3.Y Examples

- **Reasoning:** [Provide a reason for the replacement. e.g., "The new examples teach the agent the project's specific file structure..."]
- **Instruction:** Replace the entire content of the `# Examples` section with the following Markdown block:

` ``markdown
# Examples (Illustrating Tone and Workflow)
...
... (all the new example content goes here) ...
...
` ``

```

---

**Final Review:**

Before outputting the final document, review your generated changelog to ensure it is a complete and accurate representation of all changes. Verify that every difference between the two source files is accounted for under the correct category (Removed, Retained, or Modified) and that the instructions are clear and unambiguous.
