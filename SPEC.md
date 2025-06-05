# Blockscout MCP Server

This server wraps Blockscout APIs and exposes blockchain data—balances, tokens, NFTs, contract metadata—via MCP so that AI agents and tools (like Claude, Cursor, or IDEs) can access and analyze it contextually.

## Technical details

- The server is built using [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and Httpx.

### Operational Modes

The Blockscout MCP Server supports two operational modes:

1. **Stdio Mode (Default)**:
   - Designed for integration with MCP hosts/clients (Claude Desktop, Cursor, MCP Inspector, etc.)
   - Uses stdin/stdout communication following the MCP JSON-RPC 2.0 protocol
   - Automatically spawned and managed by MCP clients
   - Provides session-based interaction with progress tracking and context management

2. **HTTP Streamable Mode**:
   - Modern HTTP-based mode using the same MCP JSON-RPC 2.0 protocol over HTTP
   - Stateless operation with JSON responses for improved scalability
   - Convenient for testing with standard HTTP tools (curl, Postman, etc.) especially by AI agents and coding assistants
   - Not yet universally supported by all MCP clients, but growing in adoption

Both modes provide identical functionality and tool capabilities, differing only in the transport mechanism.

### Architecture and Data Flow

```mermaid
sequenceDiagram
    participant AI as MCP Host
    participant MCP as MCP Server
    participant BENS as Blockscout ENS Service
    participant CS as Chainscout
    participant BS as Blockscout Instance

    AI->>MCP: __get_instructions__
    MCP-->>AI: Custom instructions

    AI->>MCP: get_address_by_ens_name
    MCP->>BENS: Forward ENS name resolution request
    BENS-->>MCP: Address response
    MCP-->>AI: Formatted address

    AI->>MCP: get_chains_list
    MCP->>CS: Request available chains
    CS-->>MCP: List of chains
    MCP-->>AI: Formatted chains list

    Note over AI: Host selects chain_id as per the user's initial prompt

    AI->>MCP: get_latest_block with chain_id
    MCP->>CS: GET /api/chains/:id
    CS-->>MCP: Chain metadata (includes Blockscout URL)
    MCP->>BS: Request to Blockscout API
    BS-->>MCP: Block data
    MCP-->>AI: Formatted block information
```

### Workflow Description

1. **Instructions Retrieval**:
   - MCP Host requests custom instructions via `__get_instructions__`
   - MCP Server provides context-specific guidance

2. **ENS Resolution**:
   - MCP Host requests address resolution via `get_address_by_ens_name`
   - MCP Server forwards the request to Blockscout ENS Service
   - Response is processed and formatted before returning to the agent

3. **Chain Selection**:
   - MCP Host requests available chains via `get_chains_list`
   - MCP Server retrieves chain data from Chainscout
   - MCP Host selects appropriate chain based on user needs

4. **Blockchain Data Retrieval**:
   - MCP Host requests blockchain data (e.g., `get_latest_block`) with specific chain_id
   - MCP Server queries Chainscout for chain metadata including Blockscout instance URL
   - MCP Server forwards the request to the appropriate Blockscout instance
   - Response is processed and formatted before returning to the agent

### Key Architectural Decisions

1. **Tool Selection and Context Optimization**:
   - Not all Blockscout API endpoints are exposed as MCP tools
   - The number of tools is deliberately kept minimal to prevent diluting the LLM context
   - Too many tools make it difficult for the LLM to select the most appropriate one for a given user prompt
   - Some MCP Hosts (e.g., Cursor) have hard limits on the number of tools (capped at 50)
   - Multiple MCP servers might be configured in a client application, with each server providing its own tool descriptions
   - Tool descriptions are limited to 1024 characters to minimize context consumption

2. **Response Processing and Optimization**:
   - Raw Blockscout API responses are not forwarded directly to the MCP Host
   - Responses are processed to extract only tool-relevant data before returning to the MCP Host
   - This approach prevents overwhelming the LLM context window with excessive blockchain data
   - For example, token list responses that could contain hundreds of entries are filtered and formatted to include only essential information

3. **Instructions Delivery Workaround**:
   - Although the MCP specification defines an `instructions` field in the initialization response (per [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle#initialization)), current MCP Host implementations (e.g., Claude Desktop) do not reliably use these instructions
   - The `__get_instructions__` tool serves as a workaround for this limitation
   - The tool's description forces the MCP Host to call it before any other tools in the session
   - These custom instructions are crucial for providing the LLM with blockchain-specific context
   - Instructions could include information about chain IDs, common error handling patterns, and examples of how to reason about blockchain data and DeFi protocols
