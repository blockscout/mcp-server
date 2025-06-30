# Agent Rules Overview

This directory `.cursor/rules` contains rule files that govern the behavior and guidelines for AI agents working on the Blockscout MCP Server project.

## Rule Application Guidelines

AI agents should consult the appropriate rule files based on the context of their work. Here are the specific guidelines for when to apply each rule:

### Always Apply First

- **Always read** `.cursor/rules/000-role-and-task.mdc` since it defines the AI agent's role and the task it is performing
- **Always read** `.cursor/rules/010-implementation-rules.mdc` and resources mentioned in it before answering questions about the project or suggesting any changes

### MCP Tool Development

- **Follow** `.cursor/rules/110-new-mcp-tool.mdc` whenever creating new MCP tool functions or modifying existing  ones
- **Apply** `.cursor/rules/120-mcp-tool-arguments.mdc` rules to the tool's parameters list whenever modifying existing MCP tool functions
- **Follow** `.cursor/rules/130-version-management.mdc` when updating the version of the MCP server
- **Apply** `.cursor/rules/140-tool-description.mdc` rules to the tool's description field whenever creating a new MCP tool or updating an existing one

### Testing & Development

- **Follow** `.cursor/rules/200-development-testing-workflow.mdc` testing workflow whenever making ANY code changes to the MCP server (new features, bug fixes, modifications, refactoring, or test updates)
- **Before modifying** any unit test files within `tests/tools/` or adding new unit tests, follow guidelines from `.cursor/rules/210-unit-testing-guidelines.mdc`
- **Before working** with integration test files within `tests/integration/`, consult `.cursor/rules/220-integration-testing-guidelines.mdc`

### Code Quality & Formatting

- **Apply** `.cursor/rules/300-ruff-lint-and-format.mdc` when identifying and fixing linting and formatting issues

### Meta Operations

- **Must follow** `.cursor/rules/900-rules-maintenance.mdc` when creating, modifying, or deleting any rule files in `.cursor/rules/`
