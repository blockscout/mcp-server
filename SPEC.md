# Blockscout MCP Server

This server wraps Blockscout APIs and exposes blockchain data—balances, tokens, NFTs, contract metadata—via MCP so that AI agents and tools (like Claude, Cursor, or IDEs) can access and analyze it contextually.

## Technical details

- The server is built using [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and Httpx.

### Operational Modes

The Blockscout MCP Server supports two primary operational modes:

1. **Stdio Mode (Default)**:
   - Designed for integration with MCP hosts/clients (Claude Desktop, Cursor, MCP Inspector, etc.)
   - Uses stdin/stdout communication following the MCP JSON-RPC 2.0 protocol
   - Automatically spawned and managed by MCP clients
   - Provides session-based interaction with progress tracking and context management

2. **HTTP Mode**:
   - Enabled with the `--http` flag.
   - By default, this mode provides a pure MCP-over-HTTP endpoint at `/mcp`, using the same JSON-RPC 2.0 protocol as stdio mode.
   - While it is stateless and streams Server‑Sent Events (SSE, text/event-stream) rather than prettified JSON, it is still convenient for testing and integration (e.g., using `curl` or `Insomnia`).

   The HTTP mode can be optionally extended to serve additional web and REST API endpoints. This is disabled by default and can be enabled by providing the `--rest` flag at startup.

3. **Extended HTTP Mode (with REST API and Web Pages)**:
   - Enabled by using the `--rest` flag in conjunction with `--http`.
   - This mode extends the standard HTTP server to include additional, non-MCP endpoints:
     - A simple landing page at `/` with human-readable instructions.
     - A health check endpoint at `/health`.
     - A machine-readable policy file at `/llms.txt` for AI crawlers.
     - A versioned REST API under `/v1/` that exposes the same functionality as the MCP tools.
   - This unified server approach allows both MCP clients and traditional REST clients to interact with the same application instance, ensuring consistency and avoiding code duplication.

The core tool functionality is identical across all modes; only the transport mechanism and available endpoints differ.

### Architecture and Data Flow

```mermaid
sequenceDiagram
    participant AI as MCP Host
    participant MCP as MCP Server
    participant BENS as ENS Service
    participant CS as Chainscout
    participant BS as Blockscout Instance
    participant Metadata as Metadata Service

    AI->>MCP: __unlock_blockchain_analysis__
    MCP-->>AI: Custom instructions

    AI->>MCP: get_address_by_ens_name
    MCP->>BENS: Forward ENS name resolution request
    BENS-->>MCP: Address response
    MCP-->>AI: Formatted address

    AI->>MCP: get_chains_list
    MCP->>CS: Request available chains
    CS-->>MCP: List of chains
    MCP->>MCP: Cache chain metadata
    MCP-->>AI: Formatted chains list

    Note over AI: Host selects chain_id as per the user's initial prompt

    AI->>MCP: Tool request with chain_id
    MCP->>CS: GET /api/chains/:id
    CS-->>MCP: Chain metadata (includes Blockscout URL)
    par Concurrent API Calls (when applicable)
        MCP->>BS: Request to Blockscout API (Basic Info)
        BS-->>MCP: Primary data response
    and
        MCP->>BS: Request to Blockscout API (First Transaction)
        BS-->>MCP: First transaction response
    and
        MCP->>Metadata: Request to Metadata API (for enriched data)
        Metadata-->>MCP: Metadata response
    end
    MCP-->>AI: Formatted & combined information
```

### REST API Data Flow (Extended HTTP Mode)

When the server runs in extended HTTP mode (`--http --rest`), it provides additional REST endpoints alongside the core MCP functionality. The REST endpoints are thin wrappers that call the same underlying tool functions used by the MCP server.

```mermaid
sequenceDiagram
    participant REST as REST Client
    participant MCP as MCP Server
    participant CS as Chainscout
    participant BS as Blockscout Instance

    Note over REST, MCP: Static Endpoints
    REST->>MCP: GET /
    MCP-->>REST: HTML Landing Page

    REST->>MCP: GET /health
    MCP-->>REST: {"status": "ok"}

    Note over REST, MCP: REST API Endpoint (calls same tool function as MCP)
    REST->>MCP: GET /v1/get_block_number?chain_id=1
    Note over MCP: REST wrapper calls get_block_number() tool function
    MCP->>CS: GET /api/chains/1
    CS-->>MCP: Chain metadata (includes Blockscout URL)
    MCP->>BS: GET /api/v2/blocks/latest
    BS-->>MCP: Block data response
    MCP-->>REST: JSON Response (ToolResponse format)
```

### Unified Server Architecture

The `FastMCP` server from the MCP Python SDK is built on top of FastAPI, which allows for the registration of custom routes. When running in the extended HTTP mode (`--http --rest`), the server leverages this capability to add non-MCP endpoints directly to the `FastMCP` instance.

- **Single Application Instance**: The `FastMCP` server itself serves all traffic, whether it's from an MCP client to `/mcp` or a REST client to `/v1/...`. There is no need to mount a separate application.
- **Shared Business Logic**: The REST API endpoints are thin wrappers that directly call the same underlying tool functions used by the MCP server. This ensures that any bug fix or feature enhancement to a tool is immediately reflected in both interfaces.
- **Centralized Routing**: All routes, both for MCP and the REST API, are handled by the single `FastMCP` application instance.

This architecture provides the flexibility of a multi-protocol server without the complexity of running multiple processes or duplicating code, all while using the built-in features of the MCP Python SDK.

### Workflow Description

1. **Instructions Retrieval**:
   - MCP Host requests custom instructions via `__unlock_blockchain_analysis__`
   - MCP Server provides context-specific guidance

2. **ENS Resolution**:
   - MCP Host requests address resolution via `get_address_by_ens_name`
   - MCP Server forwards the request to Blockscout ENS Service
   - Response is processed and formatted before returning to the agent

3. **Chain Selection**:
   - MCP Host requests available chains via `get_chains_list`
   - MCP Server retrieves chain data from Chainscout.
   - The snapshot is cached in-process with a TTL (configurable via `BLOCKSCOUT_CHAINS_LIST_TTL_SECONDS`).
   - The per-chain `ChainCache` is warmed via `bulk_set` on each refresh.
   - Concurrent refreshes are deduplicated with an async lock.
   - MCP Host selects appropriate chain based on user needs

4. **Optimized Data Retrieval with Concurrent API Calls**:
   - The MCP Server employs concurrent API calls as a performance optimization whenever tools need data from multiple sources. Examples include:
     - `get_address_info`: Executes three concurrent requests to gather a comprehensive profile in a single turn:
       1. **Address Info**: Basic on-chain data from Blockscout (balance, contract status).
       2. **First Transaction**: Specific request (`?sort=block_number&order=asc`) to identify the account's inception block and timestamp.
       3. **Metadata**: Public tags and name resolution from the Metadata API.
       *Robustness Note*: The server employs a "partial success" strategy for this tool. Failures in fetching metadata or first transaction details are caught gracefully and reported in the response `notes` field, ensuring the primary address information is always returned.
     - `get_block_info` with transactions: Concurrent requests for block data and transaction list from the same Blockscout instance
   - This approach significantly reduces response times by parallelizing independent API calls rather than making sequential requests. The server combines all responses into a single, comprehensive response for the agent.

5. **Blockchain Data Retrieval**:
   - MCP Host requests blockchain data (e.g., `get_block_number`) with specific chain_id, optionally requesting progress updates
   - MCP Server, if progress is requested, reports starting the operation
   - MCP Server queries Chainscout for chain metadata including Blockscout instance URL
   - MCP Server reports progress after resolving the Blockscout URL
   - MCP Server forwards the request to the appropriate Blockscout instance
   - For potentially long-running API calls (e.g., advanced transaction filters), MCP Server provides periodic progress updates every 15 seconds (configurable via `BLOCKSCOUT_PROGRESS_INTERVAL_SECONDS`) showing elapsed time and estimated duration
   - MCP Server reports progress after fetching data from Blockscout
   - Response is processed and formatted before returning to the agent

### Key Architectural Decisions

1. **Unified Server via MCP SDK Extensibility**:
   - To support both MCP and a traditional REST API without duplicating logic, the server leverages the extensibility of the `FastMCP` class from the MCP Python SDK. This is motivated by several integration scenarios:
     - **Gateway Integration**: To enable easier integration with API gateways and marketplaces like Higress.
     - **AI-Friendly Stop-Gap**: To provide an AI-friendly alternative to the raw Blockscout API.
     - **Non-MCP Agent Support**: To allow agents without native MCP support to use the server's functionality.
   - The core MCP tool functions (e.g., `get_block_number`) serve as the single source of truth for business logic.
   - The REST API endpoints under `/v1/` are simple wrappers that call these tool functions. They are registered directly with the `FastMCP` instance using its `custom_route` method.
   - This approach ensures consistency between the two protocols, simplifies maintenance, and allows for a single deployment process.
   - This extended functionality is opt-in via a `--rest` command-line flag to maintain the server's primary focus as an MCP-first application.
   - **Context-Aware Safety**: The server distinguishes between "MCP Mode" (AI consumption) and "REST Mode" (script consumption) to apply appropriate safety guards. For example, large raw data dumps are blocked for AI agents to prevent context exhaustion but can be explicitly allowed for REST clients via control headers.

2. **Tool Selection and Context Optimization**:
   - Not all Blockscout API endpoints are exposed as MCP tools
   - The number of tools is deliberately kept minimal to prevent diluting the LLM context
   - Too many tools make it difficult for the LLM to select the most appropriate one for a given user prompt
   - Some MCP Hosts (e.g., Cursor) have hard limits on the number of tools (capped at 50)
   - Multiple MCP servers might be configured in a client application, with each server providing its own tool descriptions
   - Tool descriptions are limited to 1024 characters to minimize context consumption

3. **The Standardized `ToolResponse` Model**

   To provide unambiguous, machine-readable responses, the server enforces a standardized, structured response format for all tools. This moves away from less reliable string-based outputs and aligns with modern API best practices.

   Every tool in the server returns a `ToolResponse` object. This Pydantic model serializes to a clean JSON structure, which clearly separates the primary data payload from associated metadata.

   The core structure is as follows:

   - `data`: The main data payload of the tool's response. The schema of this field can be specific to each tool.
   - `data_description`: An optional list of strings that explain the structure, fields, or conventions of the `data` payload (e.g., "The `method_call` field is actually the event signature...").
   - `notes`: An optional list of important contextual notes, such as warnings about data truncation or data quality issues. This field includes guidance on how to retrieve full data if it has been truncated.
   - `instructions`: An optional list of suggested follow-up actions for the LLM to plan its next steps. When pagination is available, the server automatically appends pagination instructions to motivate LLMs to fetch additional pages.
   - `pagination`: An optional object that provides structured information for retrieving the next page of results.

   This approach provides immense benefits, including clarity for the AI, improved testability, and a consistent, predictable API contract.

   **Example: Comprehensive ToolResponse Structure**

   This synthetic example demonstrates all features of the standardized `ToolResponse` format that tools use to communicate with the AI agent. It shows how the server structures responses with the primary data payload, contextual metadata, pagination, and guidance for follow-up actions.

    ```json
    {
      "data": [
        {
          "block_number": 19000000,
          "transaction_hash": "0x1a2b3c4d5e6f...",
          "token_symbol": "USDC",
          "amount": "1000000000",
          "from_address": "0xa1b2c3d4e5f6...",
          "to_address": "0xf6e5d4c3b2a1...",
          "raw_data": "0x1234...",
          "raw_data_truncated": true,
          "decoded_data": {
            "method": "transfer",
            "parameters": [
              {"name": "to", "value": "0xf6e5d4c3b2a1...", "type": "address"},
              {"name": "amount", "value": "1000000000", "type": "uint256"}
            ]
          }
        }
      ],
      "data_description": [
        "Response Structure:",
        "- `block_number`: Block height where the transaction was included",
        "- `token_symbol`: Token ticker (e.g., USDC, ETH, WBTC)",
        "- `amount`: Transfer amount in smallest token units (wei for ETH)",
        "- `raw_data`: Transaction input data (hex encoded). **May be truncated.**",
        "- `raw_data_truncated`: Present when `raw_data` field has been shortened",
        "- `decoded_data`: Human-readable interpretation of the raw transaction data"
      ],
      "notes": [
        "Large data fields have been truncated to conserve context (indicated by `*_truncated: true`).",
        "For complete untruncated data, retrieve it directly:",
        "`curl \"https://eth.blockscout.com/api/v2/transactions/0x1a2b3c4d5e6f.../raw-trace\"`"
      ],
      "instructions": [
        "Use `get_address_info` to get detailed information about any address in the results",
        "Use `get_transaction_info` to get full transaction details including gas usage and status",
        "⚠️ MORE DATA AVAILABLE: Use pagination.next_call to get the next page.",
        "Continue calling subsequent pages if you need comprehensive results."
      ],
      "pagination": {
        "next_call": {
          "tool_name": "get_address_transactions", 
          "params": {
            "chain_id": "1",
            "address": "0xa1b2c3d4e5f6...",
            "cursor": "eyJibG9ja19udW1iZXIiOjE4OTk5OTk5LCJpbmRleCI6NDJ9"
          }
        }
      }
    }
    ```

4. **Async Web3 Connection Pool**:
   - The server uses a custom `AsyncHTTPProviderBlockscout` and `Web3Pool` to interact with Blockscout's JSON-RPC interface.
   - Connection pooling reuses TCP connections, reducing latency and resource usage.
   - The provider ensures request IDs never start at zero and normalizes parameters to lists for Blockscout compatibility.
   - A shared `aiohttp` session enforces global and per-host connection limits to prevent overload.

5. **Blockscout-Hosted Chain Filtering**:

   The `get_chains_list` tool intentionally returns only chains that are hosted
   by the Blockscout team. This ensures a consistent feature set, stable service
   levels, and the ability to authenticate requests from the MCP server. Chains
   without an official Blockscout instance are omitted.

6. **Response Processing and Context Optimization**:

   The server employs a comprehensive strategy to **conserve LLM context** by intelligently processing API responses before forwarding them to the MCP Host. This prevents overwhelming the LLM context window with excessive blockchain data, ensuring efficient tool selection and reasoning.

   **Core Approach:**
   - Raw Blockscout API responses are never forwarded directly to the MCP Host
   - All responses are processed to extract only tool-relevant data
   - Large datasets (e.g., token lists with hundreds of entries) are filtered and formatted to include only essential information
   - Contract source code is not returned by tools to conserve context; when contract metadata is needed, only the ABI may be returned (sources are omitted).

   **Specific Optimizations:**

    **a) Address Object Simplification:**
    Many Blockscout API endpoints return addresses as complex JSON objects containing hash, name, contract flags, public tags, and other metadata. To conserve LLM context, the server systematically simplifies these objects into single address strings (e.g., `"0x123..."`) before returning responses. This approach:

    - **Reduces Context Consumption**: A single address string uses significantly less context than a full address object with multiple fields
    - **Encourages Compositional Tool Use**: When detailed address information is needed, the AI is guided to use dedicated tools like `get_address_info`
    - **Maintains Essential Functionality**: The core address hash is preserved, which is sufficient for most blockchain operations

    **b) Opaque Cursor Strategy for Pagination:**
    For handling large, paginated datasets, the server uses an **opaque cursor** strategy that avoids exposing multiple, complex pagination parameters (e.g., `page`, `offset`, `items_count`) in tool signatures and responses. This approach provides several key benefits:

    - **Context Conservation**: A single cursor string consumes significantly less LLM context than a list of individual parameters.
    - **Improved Robustness**: It treats pagination as an atomic unit, preventing the AI from incorrectly constructing or omitting parameters for the next request.
    - **Simplified Tool Signatures**: Tool functions only need one optional `cursor: str` argument for pagination, keeping their schemas clean.

    **Mechanism:**
    When the Blockscout API returns a `next_page_params` dictionary, the server serializes this dictionary into a compact JSON string, which is then Base64URL-encoded. This creates a single, opaque, and URL-safe string that serves as the cursor for the next page.

    **Example:**

    - **Blockscout API `next_page_params`:**

       ```json
       { "block_number": 18999999, "index": 42, "items_count": 50 }
       ```

    - **Generated Opaque Cursor:**
       `eyJibG9ja19udW1iZXIiOjE4OTk5OTk5LCJpbmRleCI6NDIsIml0ZW1zX2NvdW50Ijo1MH0`

    - **Final Tool Response (JSON):**

      ```json
      {
        "data": [...],
        "pagination": {
          "next_call": {
            "tool_name": "direct_api_call",
            "params": {
              "chain_id": "1",
              "endpoint_path": "/api/v2/transactions/0x.../logs",
              "cursor": "eyJibG9ja19udW1iZXIiOjE4OTk5OTk5LCJpbmRleCI6NDIsIml0ZW1zX2NvdW50Ijo1MH0"
            }
          }
        }
      }
      ```

    **c) Response Slicing and Context-Aware Pagination:**

    To prevent overwhelming the LLM with long lists of items (e.g., token holdings, transaction logs), the server implements a response slicing strategy. This conserves context while ensuring all data remains accessible through robust pagination.

    **Basic Slicing Mechanism:**

    - The server fetches a full page of data from the Blockscout API (typically 50 items) but returns only a smaller, configurable slice to the client (e.g., 10 items). If the original response contained more items than the slice size, pagination is initiated.
    - **Cursor Generation**: Instead of using the `next_page_params` directly from the Blockscout API (which would skip most of the fetched items), the server generates a new pagination cursor based on the **last item of the returned slice**. This ensures the next request starts exactly where the previous one left off, providing seamless continuity.
    - **Configuration**: The size of the slice returned to the client is configurable via environment variables (e.g., `BLOCKSCOUT_*_PAGE_SIZE`), allowing for fine-tuning of context usage.

    **Advanced Multi-Page Fetching with Filtering:**
    For tools that apply significant filtering (e.g., `get_transactions_by_address` which excludes token transfers), the server implements a sophisticated multi-page fetching strategy to handle cases where filtering removes most items from each API page:

    - **Smart Pagination Logic**: The server fetches up to 10 consecutive full-size pages from the Blockscout API, filtering and accumulating items until it has enough for a meaningful client response.
    - **Sparse Data Detection**: If after fetching 10 pages the last page contained no filtered items and the accumulated results are still insufficient for a full client page, the data is considered "too sparse" and pagination is terminated to avoid infinite loops with minimal results.
    - **Pagination Decision**: The server offers pagination to the client only when:
      1. It has accumulated more than the target page size (definitive evidence of more data), OR
      2. It reached the 10-page limit AND the last fetched page contained items AND the API indicates more pages are available (likely more data)
    - **Efficiency Balance**: This approach balances network efficiency (fetching larger chunks) with context efficiency (returning smaller slices) while handling the complex reality of heavily filtered blockchain data.

    This strategy combines the network efficiency of fetching larger data chunks from the backend with the context efficiency of providing smaller, digestible responses to the AI.

    **d) Automatic Pagination Instructions for LLM Guidance:**

    To address the common issue of LLMs ignoring structured pagination data, the server implements a multi-layered approach to ensure LLMs actually use pagination when available:

    - **Enhanced General Rules**: Server instructions include explicit pagination handling rules that LLMs receive upfront
    - **Automatic Instruction Generation**: When a tool response includes pagination, the server automatically appends motivational instructions to the `instructions` field (e.g., "⚠️ MORE DATA AVAILABLE: Use pagination.next_call to get the next page.")
    - **Tool Description Enhancement**: All paginated tools include prominent **"SUPPORTS PAGINATION"** notices in their docstrings

    This balanced approach provides both human-readable motivation and machine-readable execution details, significantly improving the likelihood that LLMs will fetch complete datasets for comprehensive analysis.

    **e) Log Data Field Truncation**

    To prevent LLM context overflow from excessively large `data` fields in transaction logs, the server implements a smart truncation strategy.

    - **Mechanism**: If a log's `data` field (a hex string) exceeds a predefined limit of 514 characters (representing 256 bytes of data plus the '0x' prefix), it is truncated.
    - **Flagging**: A new boolean field, `data_truncated: true`, is added to the log item to explicitly signal that the data has been shortened.
    - **Decoded Truncation**: Oversized string values inside the `decoded` dictionary are recursively replaced with `{"value_sample": "...", "value_truncated": true}`.
    - **Guidance**: When truncation occurs, a note is added to the tool's output. This note explains the flag and provides a `curl` command template, guiding the agent on how to programmatically fetch the complete, untruncated data if required for deeper analysis.

    This approach maintains a small context footprint by default while providing a reliable "escape hatch" for high-fidelity data retrieval when necessary.

    **f) Generic Tool Strategy for Comprehensive API Coverage**

    While the existing specialized MCP tools provide high-level, optimized access to common blockchain data, they cannot cover every possible endpoint or chain-specific functionality offered by Blockscout. The challenge lies in balancing comprehensive data access with LLM context efficiency.

    **The "Tool Sprawl" Problem:**
    Introducing a dedicated tool for every niche endpoint would lead to "tool sprawl," overwhelming the LLM's context window and making effective tool selection difficult. This approach would violate the core principle of keeping the tool count minimal to maintain clear LLM reasoning and tool selection capabilities.

    **Solution - The `direct_api_call` Tool:**
    To address this challenge while maintaining context optimization, the server implements a generic `direct_api_call` tool that provides controlled access to a curated set of Blockscout API endpoints not covered by specialized tools. This approach allows AI agents to access specialized blockchain data without proliferating the core toolset.

    **Architectural Integration and Context Optimization:**

    1. **Functional Uniqueness**: The endpoints exposed via `direct_api_call` are strictly curated to *not* duplicate functionality already provided by existing, specific MCP tools. This eliminates "tool selection confusion" for the AI, ensuring that `direct_api_call` serves a complementary role rather than creating redundancy.

    2. **Context-Aware Endpoint Discovery**:
       - A primary, curated list of general and chain-specific endpoints is provided to the AI through the `__unlock_blockchain_analysis__` tool's response, ensuring immediate awareness of capabilities.
       - Context-relevant endpoints are suggested in the `instructions` field of responses from other specific tools (e.g., `get_address_info`), allowing the AI to "dig deeper" into related data only when contextually relevant.

    3. **Input Simplicity**: Curated endpoints are chosen to have relatively simple input parameters, making it easier for the AI to construct valid calls. The AI substitutes any path parameters (e.g., `{account_address}`) directly into the `endpoint_path` string.

    4. **Output Conciseness**: Endpoints that return excessively large or complex raw data payloads are generally excluded from the curated list, preventing LLM context overflow and maintaining the server's overall context optimization strategy.

    **Implementation**: The tool functions as a thin wrapper around the core `make_blockscout_request` helper. It accepts a `chain_id`, the full `endpoint_path`, optional `query_params`, and an optional `cursor` for pagination. For pagination in the response, it directly encodes the raw `next_page_params` from the Blockscout API into an opaque cursor, as the structure of these parameters can vary across arbitrary endpoints. It leverages the existing `ToolResponse` model for consistent output and integrates with the server's robust HTTP request handling and error propagation mechanisms. To ensure safety, the tool enforces a configurable response size limit (controlled by `BLOCKSCOUT_DIRECT_API_RESPONSE_SIZE_LIMIT`). In REST mode, this limit can be bypassed by setting the `X-Blockscout-Allow-Large-Response: true` header, allowing scripts to retrieve full datasets while protecting AI agents from context overflow.

    **Specialized Response Handling via Dispatcher**

    While the `direct_api_call` tool is designed to be a generic gateway, some endpoints benefit from specialized response processing to make their data more useful and context-friendly for AI agents. To accommodate this without creating new tools, `direct_api_call` implements an internal dispatcher pattern. Because the response size guard is enforced only on the generic fallback path, specialized handlers must ensure their outputs remain context-safe and do not return oversized payloads that could exhaust the LLM context window.

    - **Dispatcher (`dispatcher.py`)**: This module contains logic to match an incoming `endpoint_path` to a specific handler function. It uses a self-registering pattern where handlers use a decorator to associate themselves with a URL path regex.
    - **Handlers (`handlers/`)**: Specialized response processors are located in the `blockscout_mcp_server/tools/direct_api/handlers/` directory. Each handler is responsible for transforming a raw JSON API response into a structured `ToolResponse` with a specific data model, applying logic like data truncation, field curation, and custom pagination.

    If a matching handler is found, `direct_api_call` returns the rich, structured response from the handler. If no handler matches, it falls back to its default behavior of returning the raw, unprocessed JSON response wrapped in a generic `DirectApiData` model. This architecture allows for targeted enhancements while keeping the tool surface minimal and the system easily extensible.

    **g) Transaction Input Data Truncation**

    To handle potentially massive transaction input data, the `get_transaction_info` tool employs a multi-faceted truncation strategy.

    - **`raw_input` Truncation**: If the raw hexadecimal input string exceeds `INPUT_DATA_TRUNCATION_LIMIT`, it is shortened. A new flag, `raw_input_truncated: true`, is added to the response to signal this.
    - **`decoded_input` Truncation**: The server recursively traverses the nested `parameters` of the decoded input. Any string value (e.g., a `bytes` or `string` parameter) exceeding the limit is replaced by a structured object: `{"value_sample": "...", "value_truncated": true}`. This preserves the overall structure of the decoded call while saving significant context.
    - **Instructional Note**: If any field is truncated, a note is appended to the tool's output, providing a `curl` command to retrieve the complete, untruncated data, ensuring the agent has a path to the full information if needed.

    **h) Contract Source Code and ABI Separation:**

    To prevent LLM context overflow when exploring smart contracts, the server implements a strategic separation between ABI retrieval and source code inspection through dedicated tools with optimized access patterns.

    - **Separate ABI Tool**: The `get_contract_abi` tool provides only the contract's ABI without source code, as ABI information alone is sufficient for most contract interaction scenarios. This avoids the significant context consumption that would result from combining ABI with potentially large source code in a single response.

    - **Two-Phase Source Code Inspection**: The `inspect_contract_code` tool uses a deliberate two-phase approach for source exploration:
      - **Phase 1 (Metadata Overview)**: When called without a specific `file_name`, the tool returns contract metadata (excluding ABI to avoid duplication) and a structured source file tree. This gives the LLM a complete overview of the contract's file organization without consuming excessive context.
      - **Phase 2 (Selective File Reading)**: The LLM can then make targeted requests for specific files of interest (e.g., main contract logic) while potentially skipping standard interfaces (e.g., ERC20 implementations) that don't require inspection.

    - **Constructor Arguments Truncation**: When constructor arguments in metadata exceed size limits, they are truncated using the same strategy as described in "Transaction Input Data Truncation".

    - **Smart File Naming**: For single-file contracts (including flattened contracts), the server ensures a consistent file tree structure. When metadata doesn't provide a file name (common in Solidity contracts), the server constructs one using the pattern `<contract_name>.sol` for Solidity. For Vyper contracts, the file name is usually specified in the metadata.

    - **Response Caching**: Since contract source exploration often involves multiple sequential requests for the same contract, the server implements in-memory caching of Blockscout API responses with LRU eviction and TTL expiry. This minimizes redundant API calls and improves response times for multi-file contract inspection workflows.

    **i) Generic Tool Response Size Limit**

    For the `direct_api_call` tool, which acts as a fallback for accessing raw API endpoints, the server enforces a strict response size limit (default: 100,000 characters).

    - **Rationale**: Unlike specialized tools that curate and truncate data, this tool returns raw JSON. A massive unpaginated response could instantly exhaust the LLM's context window or cause generation failures.
    - **Enforcement**:
        - **MCP Mode (AI Agents)**: The limit is strictly enforced. If a response exceeds the limit, the tool raises a `ResponseTooLargeError` and advises the agent to use filters.
        - **REST Mode (Scripts/Middleware)**: The limit is enforced by default to prevent accidental overload. However, developers can explicitly bypass this check by including the HTTP header `X-Blockscout-Allow-Large-Response: true`.

7. **HTTP Request Robustness**

   Blockscout HTTP requests are centralized via the helper `make_blockscout_request`. To improve resilience against transient, transport-level issues observed in real-world usage (for example, incomplete chunked reads), the helper employs a small and conservative retry policy:

   - Applies only to idempotent GETs (this function is GET-only)
   - Retries up to 3 attempts on `httpx.RequestError` (transport errors)
   - Does not retry on `httpx.HTTPStatusError` (4xx/5xx responses)
   - Uses short exponential backoff between attempts (0.5s, then 1.0s)

   Configuration:
   - The maximum number of retry attempts is configurable via the environment variable `BLOCKSCOUT_BS_REQUEST_MAX_RETRIES` (default: `3`).

   This keeps API semantics intact, avoids masking persistent upstream problems, and improves reliability for both MCP tools and the REST API endpoints that proxy through the same business logic.

8. **HTTP Error Handling and Context Propagation**

   To enable AI agents to self-correct when API requests fail (e.g., due to invalid parameters like unsupported sort fields), the server implements a robust error propagation strategy.

   - **Interception**: The server intercepts standard `HTTPStatusError` exceptions raised by the underlying HTTP client.
   - **Extraction**: It parses the response body to extract detailed error messages, specifically targeting:
     - The `errors` array (JSON:API standard), combining `title`, `detail`, and `source.pointer` to provide complete context (e.g., "Invalid value: Unexpected field (at /sort)").
     - The `message` or `error` fields for generic JSON errors.
   - **Enrichment**: The generic HTTP error message (e.g., "422 Unprocessable Entity") is enriched with these specific details.
   - **Safety**: For non-JSON errors (like HTML 502 pages), the raw response text is included but strictly truncated (200 characters) to protect the LLM context window.

   This ensures that the AI receives the specific feedback needed to adjust its tool usage without overwhelming it with raw HTML or stack traces.

9. **Standardized Tool Annotations**:

    To ensure consistent behavior reporting and provide a better user experience, all MCP tools are registered with a `ToolAnnotations` object. This metadata, generated via a helper function in `blockscout_mcp_server/server.py`, serves two functions: it provides a clean, human-readable `title` for each tool, and it explicitly signals to clients that the tools are `readOnlyHint=True` (they do not modify the local environment), `destructiveHint=False`, and `openWorldHint=True` (they interact with external, dynamic APIs). This convention provides clear, uniform metadata for all tools. More about annotations for MCP tools is in [the MCP specification](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations).

10. **Research Optimization and Workflow Simplification**

   Beyond technical performance, the server is architected to minimize the "reasoning load" on AI agents by providing high-leverage metadata upfront.

   *   **Temporal Bounding**: Tools like `get_address_info` proactively fetch critical boundary data (e.g., `first_transaction_details`) that agents would otherwise have to derive through complex, multi-step discovery processes. For EOAs, the first transaction offers the most reliable account-age anchor. For contracts, the creation transaction is the better bottom line, and `creation_transaction_hash` is already surfaced in the tool's `basic_info` payload.
   *   **Strategic Anchoring**: By providing this "bottom line" information immediately, the server enables agents to construct precise, bounded queries for subsequent steps (e.g., correctly setting the `age_from` parameter in `get_transactions_by_address`).
   *   **Deferred Validator Age**: While the first validated/mined block could also serve as an account-age signal for validators, the server does not currently fetch it because Blockscout's `api/v2/addresses/{address_hash}/blocks-validated` endpoint only returns the most recent blocks and does not expose a sort-order override for earliest-first retrieval.

   This approach flattens the reasoning tree required for tasks like account age analysis or history reconstruction, allowing agents to move from "discovery" to "analysis" in a single step.

### Instructions Delivery and the `__unlock_blockchain_analysis__` Tool

#### The Initial Problem: Bypassed Server Instructions

Although the MCP specification defines an `instructions` field in the initialization response (per [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle#initialization)), empirical testing with various MCP Host implementations (e.g., Claude Desktop) revealed that these server-level instructions are not reliably processed or adhered to by the AI agent. This creates a significant challenge, as the agent lacks the essential context and operational rules needed to interact with the blockchain data tools effectively.

#### The First-Generation Workaround: `__get_instructions__`

To mitigate this, the server initially implemented a tool named `__get_instructions__`. The tool's description was designed to be highly persuasive, instructing the agent that it was a mandatory first step.

However, further testing showed this approach was insufficient. LLMs often treated the tool as optional guidance—akin to a "Read Me" file—rather than a non-negotiable prerequisite. Despite increasingly forceful descriptions, agents would frequently skip this step in their eagerness to answer the user's prompt directly, leading to suboptimal or incorrect tool usage.

#### The Revised Strategy: From Persuasion to Structural Guidance

The core issue was identified as a flaw in the interaction design: we were trying to *persuade* the agent with natural language instead of *structurally guiding* its behavior. The solution was to change the tool's fundamental identifier—its name—to create a more powerful and unambiguous signal.

The tool was renamed to `__unlock_blockchain_analysis__`.

This name was chosen deliberately for several reasons based on observed LLM behavior:

1. **Creates a Strong Semantic Imperative**: The verb "unlock" implies a necessary, state-changing action that must be performed before other operations can succeed. It reframes the tool from an optional piece of information to a functional prerequisite.

2. **Aligns with LLM's Sequential Processing**: LLMs are trained on vast amounts of code and documentation that follow a clear `initialize -> execute` or `setup -> run` pattern. The `unlock -> analyze` narrative fits this ingrained sequential model, making it a natural and logical first step for the agent to take.

3. **Provides a Coherent and Compelling Narrative**: The name, combined with a description stating that other tools are "locked," creates a simple and powerful story for the agent: "To begin my work, I must first call the `__unlock_blockchain_analysis__` tool." This is far more effective than the ambiguous `__get_instructions__` which lacks a clear call to action.

This revised strategy, which combines the action-oriented name with a direct and explicit description, has proven to be significantly more effective at ensuring the agent performs the critical initialization step. While the probabilistic nature of LLMs means no single change can guarantee 100% compliance, this approach of structural guidance has yielded far more consistent and reliable behavior than attempts at mere persuasion.

### Performance Optimizations and User Experience

#### Periodic Progress Tracking for Long-Running API Calls

The server implements sophisticated progress tracking for potentially long-running API operations, particularly for tools that query the Blockscout `/api/v2/advanced-filters` endpoint (such as `get_transactions_by_address` and `get_token_transfers_by_address`). This feature significantly improves user experience by providing real-time feedback during operations that may take 30 seconds or more.

**Technical Implementation:**

The progress tracking system uses a wrapper function (`make_request_with_periodic_progress`) that employs concurrent task execution to provide periodic updates without blocking the actual API call. The implementation leverages Python's `anyio` library for structured concurrency.

```mermaid
sequenceDiagram
    participant Tool as Tool Function
    participant Wrapper as make_request_with_periodic_progress
    participant APITask as API Call Task
    participant ProgressTask as Progress Reporting Task
    participant Client as MCP Client
    participant API as Blockscout API

    Tool->>Wrapper: Call with request_function & params
    Wrapper->>Wrapper: Create anyio.Event for coordination
    
    par Concurrent Execution
        Wrapper->>APITask: Start API call task
        APITask->>API: Make actual HTTP request
        and
        Wrapper->>ProgressTask: Start progress reporting task
        loop Every N seconds (configurable)
            ProgressTask->>ProgressTask: Calculate elapsed time
            ProgressTask->>ProgressTask: Calculate progress percentage
            ProgressTask->>Client: report_progress & info log
            ProgressTask->>ProgressTask: Sleep until next interval or completion
        end
    end
    
    API-->>APITask: Return response
    APITask->>APITask: Set completion event
    ProgressTask->>ProgressTask: Exit loop (event set)
    APITask-->>Wrapper: Return API result
    Wrapper->>Client: Final progress report (100%)
    Wrapper-->>Tool: Return API response
```

**Key Implementation Details:**

1. **Concurrent Task Management**: Uses `anyio.create_task_group()` to run the API call and progress reporting concurrently
2. **Event-Driven Coordination**: An `anyio.Event` coordinates between tasks - the progress task continues until the API task signals completion
3. **Dynamic Progress Calculation**: Progress within the current step is calculated as `min(elapsed_time / expected_duration, 1.0)` to ensure it never exceeds 100%
4. **Multi-Step Integration**: The wrapper integrates seamlessly with the overall tool progress tracking by accepting `tool_overall_total_steps` and `current_step_number` parameters
5. **Configurable Intervals**: Progress reporting frequency is configurable via `BLOCKSCOUT_PROGRESS_INTERVAL_SECONDS` (default: 15 seconds)
6. **Error Handling**: Exceptions from the API call are properly propagated while ensuring progress task cleanup

#### Enhanced Observability with Logging

The server implements two complementary forms of logging to aid both MCP clients and server operators.

#### Production-Ready Logging Configuration

The server addresses a fundamental logging issue with the MCP Python SDK, which uses Rich formatting by default. While Rich provides attractive multi-line, indented console output for development, it creates problematic logs for production environments.

The server employs a post-initialization handler replacement strategy:

1. Allow the MCP SDK to initialize normally with its Rich handlers
2. Scan all loggers to identify Rich handlers by class name and module
3. Replace Rich handlers with standard `StreamHandler` instances using clean formatting
4. Preserve all other logging behavior and configuration

This configuration is applied during server startup, ensuring clean single-line log output across all operational modes.

#### 1. Client-Facing Progress Logging

While `report_progress` is the standard for UI feedback, many MCP clients do not yet render progress notifications but do capture log messages sent via `ctx.info`. To provide essential real-time feedback for development and debugging, the server systematically pairs every progress notification with a corresponding `info` log message sent to the client.

This is achieved via a centralized `report_and_log_progress` helper function. This dual-reporting mechanism ensures that:

1. **Compliant clients** can use the structured `progress` notifications to build rich UIs.
2. **All other clients** receive human-readable log entries (e.g., `Progress: 1.0/2.0 - Step complete`), eliminating the "black box" effect during long-running operations and improving debuggability.

#### 2. Server-Side Tool Invocation Auditing

In addition to progress reporting, the server maintains a detailed audit log of all tool invocations for operational monitoring and debugging.

Implemented via the `@log_tool_invocation` decorator, these logs capture:

- The name of the tool that was called.
- The arguments provided to the tool.
- The identity of the MCP client that initiated the call, including its **name**, **version**, and the **MCP protocol version** it is using.

If the client name cannot be determined from the MCP session parameters, the server falls back to the HTTP `User-Agent` header as the client identifier.

This provides a clear audit trail, helping to diagnose issues that may be specific to certain client versions or protocol implementations. For stateless calls, such as those from the REST API where no client is present, this information is gracefully omitted.

In HTTP streamable mode, an allowlisted intermediary identifier can annotate the client name. The header name is configured via `BLOCKSCOUT_INTERMEDIARY_HEADER` (default: `Blockscout-MCP-Intermediary`) and allowed values via `BLOCKSCOUT_INTERMEDIARY_ALLOWLIST` (default: `ClaudeDesktop,HigressPlugin`). After trimming, collapsing whitespace, and validating length (≤16), the intermediary is appended to the base client name as `base/variant`. Invalid or disallowed values are ignored.

#### 3. Dual-Mode Analytics

##### Direct Analytics (via Mixpanel)

To gain insight into tool usage patterns, the server can optionally report tool invocations to Mixpanel.

- Activation (opt-in only):
  - Enabled exclusively in HTTP modes (MCP-over-HTTP and REST).
  - Requires `BLOCKSCOUT_MIXPANEL_TOKEN` to be set; otherwise analytics are disabled.

- Integration point:
  - Tracking is centralized in `blockscout_mcp_server/analytics.py` and invoked from the shared `@log_tool_invocation` decorator so every tool is tracked consistently without altering tool implementations.

- Tracked properties (per event):
  - Client IP address derived from the HTTP request, preferring proxy headers when present: `X-Forwarded-For` (first value), then `X-Real-IP`, otherwise connection `client.host`.
  - MCP client name (or the HTTP `User-Agent` when the client name is unavailable). When a valid intermediary header is present, the client name is recorded as `base/variant`.
  - MCP client version.
  - MCP protocol version.
  - Tool arguments (currently sent as-is, without truncation).
  - Call source: whether the tool was invoked by MCP or via the REST API.

- Anonymous identity (distinct_id) (as per Mixpanel's [documentation](https://docs.mixpanel.com/docs/tracking-methods/id-management/identifying-users-simplified#server-side-identity-management)):
  - A stable `distinct_id` is generated to anonymously identify unique users.
  - The fingerprint is the concatenation of: namespace URL (`https://mcp.blockscout.com/mcp`), client IP, client name, and client version.
  - This yields stable identification even when multiple clients share the same name/version (e.g., Claude Desktop) because their IPs differ.

- REST API support and source attribution:
  - The REST context mock is extended with a request context wrapper so analytics can extract IP and headers consistently (see `blockscout_mcp_server/api/dependencies.py`).
  - A `call_source` field is introduced on the REST mock context and set to `"rest"`, allowing analytics to reliably distinguish REST API calls from MCP tool calls without coupling to specific URL paths.

##### Community Telemetry (via Centralized Reporting)

- **Activation**: This mode is active on self-hosted instances in both stdio and HTTP modes, with the following conditions:
  - **Stdio mode**: Always active when `BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY` is not set to true
  - **HTTP mode**: Active only when both `BLOCKSCOUT_MIXPANEL_TOKEN` is not configured AND `BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY` is not set to true
- **Mechanism**: To understand usage in the open-source community, these instances send an anonymous, "fire-and-forget" report to a central endpoint (`POST /v1/report_tool_usage`) on the official Blockscout MCP server. This report contains the tool name, tool arguments, the MCP client name and version, the model context protocol version, and the server's version.
- **Central Processing**: The central server receives this report, uses the sender's IP address for geolocation, and forwards the event to Mixpanel with the client metadata, protocol version, and a `source` property of `"community"`. This allows us to gather valuable aggregate statistics without requiring every user to have a Mixpanel account.
- **Opt-Out**: This community reporting can be completely disabled by setting the `BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY` environment variable to `true`.

### Smart Contract Interaction Tools

This server exposes a tool for on-chain smart contract read-only state access. It uses the JSON-RPC `eth_call` semantics under the hood and aligns with the standardized `ToolResponse` model.

- **read_contract**: Executes a read-only contract call by encoding inputs per ABI and invoking `eth_call` (also used to simulate non-view/pure functions without changing state).

#### read_contract

- **RPC used**: `eth_call`.
- **Implementation**: Uses Web3.py for ABI-based input encoding and output decoding. This leverages Web3's well-tested argument handling and return value decoding.
- **ABI requirement**: Accepts the ABI of the specific function variant to call (a single ABI object for that function signature). This avoids ambiguity when contracts overload function names.
- **Function name**: The `function_name` parameter must match the `name` field in the provided function ABI. Although redundant, it is kept intentionally to improve LLM tool-selection behavior and may be removed later.
- **Arguments**: The `args` parameter is a JSON string containing an array of arguments, defaulting to `[]` when omitted. Nested structures and complex ABIv2 types are supported (arrays, tuples, structs). Argument normalization rules:
  - Addresses can be provided as 0x-prefixed strings; the tool normalizes and applies EIP-55 checksum internally.
  - Numeric strings are coerced to integers.
  - Bytes values should be provided as 0x-hex strings; nested hex strings are handled.
  - Deep recursion is applied for lists and dicts to normalize all nested values.
- **Block parameter**: Optional `block` (default: `latest`). Accepts a block number (integer or decimal string) or a tag such as `latest`.
- **Other eth_call params**: Not supported/passed. No `from`, `gas`, `gasPrice`, `value`, etc., are set by this tool.

#### Tested coverage and examples

- Complex input and output handling for nested ABIv2 types is validated against the contract `tests/integration/Web3PyTestContract.sol` deployed on Sepolia at `0xD9a3039cfC70aF84AC9E566A2526fD3b683B995B`.

#### LLM guidance

- Tool and argument descriptions explicitly instruct LLMs to:
  - Provide arguments as a JSON string containing an array (e.g., `"[\"0xabc...\"]"` for a single address)
  - Provide 0x-prefixed address strings within the array
  - Supply integers for numeric values (not quoted) when possible; numeric strings will be coerced
  - Keep bytes as 0x-hex strings within the array
- These instructions improve the likelihood of valid `eth_call` preparation and encoding.

#### Limitations

- Write operations are not supported; `eth_call` does not change state.
- No caller context (`from`) or gas simulation tuning is provided.
- Multi-function ABI arrays are not accepted for `read_contract`; provide exactly the ABI item for the intended function signature.
