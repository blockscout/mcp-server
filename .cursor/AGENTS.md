# Agent Rules Overview

This directory `.cursor/rules` contains rule files that govern the behavior and guidelines for AI agents working on the Blockscout MCP Server project.

## Rule Files

### Core Rules (000-099)

- **`000-role-and-task.mdc`** - Defines the AI agent's role and the task it is performing
- **`010-implementation-rules.mdc`** - Core implementation guidelines including project structure references, file size limits, and import placement rules

### MCP Tool Development (100-199)

- **`110-new-mcp-tool.mdc`** - Comprehensive guide for adding new MCP tool functions and patterns, including data truncation techniques
- **`120-mcp-tool-arguments.mdc`** - Rules for modifying existing MCP tool functions, emphasizing context conservation and purpose clarity
- **`130-version-management.mdc`** - Version update procedures requiring synchronization across pyproject.toml, __init__.py, and constants.py
- **`140-tool-description.mdc`** - Guidelines for writing effective tool descriptions with character limits and formatting rules

### Testing & Development (200-299)

- **`200-development-testing-workflow.mdc`** - Mandatory testing workflow for all code changes including unit tests, integration tests, and validation steps
- **`210-unit-testing-guidelines.mdc`** - Detailed unit testing patterns including mocking strategies, assertion guidelines, and file organization
- **`220-integration-testing-guidelines.mdc`** - Integration testing guidelines, including pagination tests and multi-page search best practices

### Meta Rules (900-999)

- **`900-rules-maintenance.mdc`** - Instructions for maintaining this AGENTS.md file whenever rule files are created or modified

## Usage

These rules are automatically applied by the AI agent based on the context of the work being performed. Some rules are always applied (`alwaysApply: true`), while others are contextually triggered based on file patterns or specific operations.
