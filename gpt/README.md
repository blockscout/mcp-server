# Blockscout X-Ray GPT

This directory contains files required to create a GPT in ChatGPT that integrates with the Blockscout MCP server.

## Official GPT

The official GPT is **"Blockscout X-Ray"**: <https://chatgpt.com/g/g-68a7f315edf481918641bd0ed1e60f8b-blockscout-x-ray>

## Files Description

### @instructions.md

Contains the core instructions for the GPT. The instructions incorporate the content returned by the `__unlock_blockchain_analysis__` tool, which helps the GPT with reasoning before calling any other tools.

**Important**: If the data provided by the `__unlock_blockchain_analysis__` tool is changed, the instructions must be updated accordingly.

The instructions are built following the OpenAI GPT-5 prompting guide recommendations: <https://github.com/openai/openai-cookbook/blob/main/examples/gpt-5/gpt-5_prompting_guide.ipynb>

### @action_tool_descriptions.md

Required because GPT instructions are limited to 8,000 characters. This file contains detailed descriptions of all MCP tools available to the GPT.

**Maintenance**: This file must be updated every time an MCP tool is updated or a new one is created.

### @openapi.yaml

OpenAPI 3.1.0 specification generated for the REST API endpoints provided by the MCP server. Contains short summaries of the MCP server tools and is used for GPT actions.

**Key modifications from the original MCP tool descriptions**:

- Tool parameter descriptions are modified to comply with OpenAPI 3.1.0 standards
- Tool descriptions are truncated to be less than 300 characters per OpenAPI requirements
- The `__unlock_blockchain_analysis__` endpoint is excluded since its data is incorporated directly into the GPT instructions
- Some tool parameters (specifically for `read_contract`) have modified descriptions for OpenAPI compliance

## Recommended GPT Configuration

- **Model**: GPT-5
- **Capabilities**:
  - Web Search
  - Code Interpreter and Data Analysis

## Known Issues

1. **Block time estimation**: Although clearly stated in instructions, the GPT struggles to estimate blocks by time properly.

2. **Contract read parameters**: The GPT has difficulty properly formatting input parameters (`abi` and `args`) for the `read_contract` tool, often requiring 2-3 additional action calls before understanding the correct format.
