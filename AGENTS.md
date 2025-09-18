# Blockscout MCP Server

## Project Structure

```text
mcp-server/
├── blockscout_mcp_server/      # Main Python package for the server
│   ├── __init__.py             # Makes the directory a Python package
│   ├── llms.txt                # Machine-readable guidance file for AI crawlers
│   ├── api/                    # REST API implementation
│   │   ├── __init__.py         # Initializes the api sub-package
│   │   ├── dependencies.py     # Dependency providers for the REST API
│   │   ├── helpers.py          # Shared utilities for REST API handlers
│   │   └── routes.py           # REST API route definitions
│   ├── __main__.py             # Entry point for `python -m blockscout_mcp_server`
│   ├── server.py               # Core server logic: FastMCP instance, tool registration, CLI
│   ├── templates/              # Static HTML templates for the web interface
│   │   └── index.html          # Landing page for the REST API
│   ├── config.py               # Configuration management (e.g., API keys, timeouts, cache settings)
│   ├── constants.py            # Centralized constants used throughout the application, including data truncation limits
│   ├── logging_utils.py        # Logging utilities for production-ready log formatting
│   ├── analytics.py            # Centralized Mixpanel analytics for tool invocations (HTTP mode only)
│   ├── telemetry.py            # Fire-and-forget community telemetry reporting
│   ├── client_meta.py          # Shared client metadata extraction helpers and defaults
│   ├── cache.py                # Simple in-memory cache for chain data
│   ├── web3_pool.py            # Async Web3 connection pool manager
│   ├── models.py               # Defines standardized Pydantic models for all tool responses
│   └── tools/                  # Sub-package for tool implementations
│       ├── __init__.py         # Initializes the tools sub-package
│       ├── common.py           # Shared utilities and common functionality for all tools
│       ├── decorators.py       # Logging decorators like @log_tool_invocation
│       ├── address/            # Address-related tools grouped by functionality
│       │   ├── __init__.py
│       │   ├── get_address_info.py
│       │   ├── get_address_logs.py
│       │   ├── get_tokens_by_address.py
│       │   └── nft_tokens_by_address.py
│       ├── block/
│       │   ├── __init__.py
│       │   ├── get_block_info.py
│       │   └── get_latest_block.py
│       ├── chains/
│       │   ├── __init__.py
│       │   └── get_chains_list.py
│       ├── contract/
│       │   ├── __init__.py
│       │   ├── _shared.py              # Shared helpers for contract tools
│       │   ├── get_contract_abi.py
│       │   ├── inspect_contract_code.py
│       │   └── read_contract.py
│       ├── direct_api/
│       │   ├── __init__.py
│       │   └── direct_api_call.py
│       ├── ens/
│       │   ├── __init__.py
│       │   └── get_address_by_ens_name.py
│       ├── initialization/
│       │   ├── __init__.py
│       │   └── unlock_blockchain_analysis.py
│       ├── search/
│       │   ├── __init__.py
│       │   └── lookup_token_by_symbol.py
│       └── transaction/
│           ├── __init__.py
│           ├── _shared.py             # Shared helpers for transaction tools
│           ├── get_token_transfers_by_address.py
│           ├── get_transaction_info.py
│           ├── get_transaction_logs.py
│           ├── get_transactions_by_address.py
│           └── transaction_summary.py
├── tests/                      # Test suite for all MCP tools
│   ├── integration/            # Integration tests that make real network calls
│   │   ├── __init__.py         # Marks integration as a sub-package
│   │   ├── helpers.py          # Shared utilities for integration assertions
│   │   ├── test_common_helpers.py  # Helper-level integration tests for API helpers
│   │   ├── address/            # Address tool integration tests (one file per tool)
│   │   │   ├── test_get_address_info_real.py
│   │   │   ├── test_get_address_logs_real.py
│   │   │   ├── test_get_tokens_by_address_real.py
│   │   │   └── test_nft_tokens_by_address_real.py
│   │   ├── block/
│   │   │   ├── test_get_block_info_real.py
│   │   │   └── test_get_latest_block_real.py
│   │   ├── chains/
│   │   │   └── test_get_chains_list_real.py
│   │   ├── contract/
│   │   │   ├── Web3PyTestContract.sol          # Fixture contract for live calls
│   │   │   ├── test_get_contract_abi_real.py
│   │   │   ├── test_inspect_contract_code_real.py
│   │   │   ├── test_read_contract_real.py
│   │   │   └── web3py_test_contract_abi.json   # ABI fixture for Web3Py tests
│   │   ├── direct_api/
│   │   │   └── test_direct_api_call_real.py
│   │   ├── ens/
│   │   │   └── test_get_address_by_ens_name_real.py
│   │   ├── search/
│   │   │   └── test_lookup_token_by_symbol_real.py
│   │   └── transaction/
│   │       ├── test_get_token_transfers_by_address_real.py
│   │       ├── test_get_transaction_info_real.py
│   │       ├── test_get_transaction_logs_real.py
│   │       ├── test_get_transactions_by_address_real.py
│   │       └── test_transaction_summary_real.py
│   ├── api/                      # Unit tests for the REST API
│   │   └── test_routes.py        # Tests for static API route definitions
│   ├── test_server.py            # Tests for server CLI and startup logic
│   ├── test_models.py            # Tests for Pydantic response models
│   └── tools/                  # Unit test modules for each tool implementation
│       ├── address_tools/      # Tests for address-related MCP tools
│       │   ├── test_get_address_info.py        # Tests for get_address_info
│       │   ├── test_get_address_logs.py              # Tests for get_address_logs
│       │   ├── test_get_tokens_by_address.py         # Tests for get_tokens_by_address
│       │   ├── test_nft_tokens_by_address.py         # Tests for nft_tokens_by_address
│       │   └── test_nft_tokens_by_address_pagination.py  # Pagination scenarios for nft_tokens_by_address
│       ├── block_tools/        # Tests for block-related MCP tools
│       │   ├── test_get_block_info.py          # Tests for get_block_info
│       │   └── test_get_latest_block.py        # Tests for get_latest_block
│       ├── chains_tools/       # Tests for chain-related MCP tools
│       │   └── test_get_chains_list.py         # Tests for get_chains_list
│       ├── contract_tools/     # Tests for contract-related MCP tools
│       │   ├── test_fetch_and_process_contract.py  # Tests for fetch_and_process_contract
│       │   ├── test_get_contract_abi.py        # Tests for get_contract_abi
│       │   ├── test_inspect_contract_code.py   # Tests for inspect_contract_code
│       │   └── test_read_contract.py           # Tests for read_contract
│       ├── transaction_tools/  # Tests for transaction-related MCP tools
│       │   ├── test_get_token_transfers_by_address.py      # Tests for get_token_transfers_by_address
│       │   ├── test_get_transaction_info.py        # Tests for get_transaction_info
│       │   ├── test_get_transaction_logs.py        # Tests for get_transaction_logs
│       │   ├── test_get_transaction_logs_pagination.py  # Pagination-focused logs tests
│       │   ├── test_get_transactions_by_address.py      # Tests for get_transactions_by_address
│       │   ├── test_get_transactions_by_address_pagination.py  # Pagination-focused transaction tests
│       │   ├── test_helpers.py                     # Tests for transaction helper utilities
│       │   └── test_transaction_summary.py         # Tests for transaction_summary
│       ├── direct_api_tools/   # Tests for the direct API MCP tool
│       │   └── test_direct_api_call.py  # Tests for direct_api_call
│       ├── ens_tools/          # Tests for ENS-related MCP tools
│       │   └── test_get_address_by_ens_name.py  # Tests for get_address_by_ens_name
│       ├── initialization_tools/  # Tests for initialization MCP tools
│       │   └── test___unlock_blockchain_analysis__.py  # Tests for __unlock_blockchain_analysis__
│       ├── search_tools/       # Tests for search-related MCP tools
│       │   └── test_lookup_token_by_symbol.py  # Tests for lookup_token_by_symbol
│       ├── test_common.py            # Tests for shared utility functions
│       ├── test_common_truncate.py   # Tests for truncation helpers
│       └── test_decorators.py        # Tests for logging decorators
├── dxt/                        # Desktop Extension (.dxt) package for Claude Desktop
│   ├── README.md               # DXT-specific documentation and packaging instructions
│   ├── manifest.json           # Extension manifest with metadata and tool definitions
│   └── blockscout.png          # Extension icon file
├── gpt/                        # ChatGPT GPT integration package for "Blockscout X-Ray"
│   ├── README.md               # GPT-specific documentation and configuration instructions
│   ├── instructions.md         # Core GPT instructions incorporating `__unlock_blockchain_analysis__` content
│   ├── action_tool_descriptions.md # Detailed descriptions of all MCP tools (due to GPT 8k char limit)
│   └── openapi.yaml            # OpenAPI 3.1.0 specification for REST API endpoints used by GPT actions
├── Dockerfile                  # For building the Docker image
├── pytest.ini                  # Pytest configuration (excludes integration tests by default)
├── API.md                      # Detailed documentation for the REST API
├── README.md                   # Project overview, setup, and usage instructions
├── SPEC.md                     # Technical specification and architecture documentation
├── TESTING.md                  # Testing instructions for HTTP mode with curl commands
├── pyproject.toml              # Project metadata and dependencies (PEP 517/518)
└── .env.example                # Example environment variables
```

## Overview of Components

1. **`mcp-server/` (Root Directory)**
    * **`README.md`**:
        * Provides a comprehensive overview of the project.
        * Includes detailed instructions for local setup (installing dependencies, setting environment variables) and running the server.
        * Contains instructions for building and running the server using Docker.
        * Lists all available tools and their functionalities.
    * **`API.md`**:
        * Provides detailed documentation for all REST API endpoints.
        * Includes usage examples, parameter descriptions, and information on the standard response structure.
    * **`SPEC.md`**:
        * Contains technical specifications and detailed architecture documentation.
        * Outlines the system design, components interaction, and data flow.
        * Describes key architectural decisions and their rationales.
    * **`TESTING.md`**:
        * Provides comprehensive instructions for testing the MCP server locally using HTTP mode.
        * Contains curl command examples for testing all major tools and functionality.
        * Serves as a practical guide for developers to understand and test the server's capabilities.
    * **`pyproject.toml`**:
        * Manages project metadata (name, version, authors, etc.).
        * Lists project dependencies, which will include:
            * `mcp[cli]`: The Model Context Protocol SDK for Python with CLI support.
            * `httpx`: For making asynchronous HTTP requests to Blockscout APIs.
            * `pydantic`: For data validation and settings management (used by `mcp` and `config.py`).
            * `pydantic-settings`: For loading configuration from environment variables.
            * `anyio`: For async task management and progress reporting.
            * `uvicorn`: For HTTP Streamable mode ASGI server.
            * `typer`: For CLI argument parsing (included in `mcp[cli]`).
        * Lists optional test dependencies:
            * `pytest`: Main testing framework for unit tests.
            * `pytest-asyncio`: Support for async test functions.
            * `pytest-cov`: For code coverage reporting.
        * Configures the build system (e.g., Hatchling).
    * **`Dockerfile`**:
        * Defines the steps to create a Docker image for the MCP server.
        * Specifies the base Python image.
        * Copies the application code into the image.
        * Installs Python dependencies listed in `pyproject.toml`.
        * Sets up necessary environment variables (can be overridden at runtime).
        * Defines the `CMD` to run the MCP server in stdio mode by default (`python -m blockscout_mcp_server`).
    * **`.env.example`**:
        * Provides a template for users to create their own `.env` file for local development.
        * Lists all required environment variables, such as:
            * `BLOCKSCOUT_BS_API_KEY`: API key for Blockscout API access (if required).
            * `BLOCKSCOUT_BS_TIMEOUT`: Timeout for Blockscout API requests.
            * `BLOCKSCOUT_BENS_URL`: Base URL for the BENS (Blockscout ENS) API.
            * `BLOCKSCOUT_BENS_TIMEOUT`: Timeout for BENS API requests.
            * `BLOCKSCOUT_METADATA_URL`: Base URL for the Blockscout Metadata API.
            * `BLOCKSCOUT_METADATA_TIMEOUT`: Timeout for Metadata API requests.
            * `BLOCKSCOUT_CHAINSCOUT_URL`: URL for the Chainscout API (for chain resolution).
            * `BLOCKSCOUT_CHAINSCOUT_TIMEOUT`: Timeout for Chainscout API requests.
            * `BLOCKSCOUT_CHAIN_CACHE_TTL_SECONDS`: Time-to-live for chain resolution cache.
            * `BLOCKSCOUT_CHAINS_LIST_TTL_SECONDS`: Time-to-live for the Chains List cache.
            * `BLOCKSCOUT_PROGRESS_INTERVAL_SECONDS`: Interval for periodic progress updates in long-running operations.
            * `BLOCKSCOUT_NFT_PAGE_SIZE`: Page size for NFT token queries (default: 10).
            * `BLOCKSCOUT_LOGS_PAGE_SIZE`: Page size for address logs queries (default: 10).
            * `BLOCKSCOUT_ADVANCED_FILTERS_PAGE_SIZE`: Page size for advanced filter queries (default: 10).

2. **`dxt/` (Desktop Extension Package)**
    * This directory contains the Desktop Extension (.dxt) package for Claude Desktop integration.
    * **`README.md`**:
        * Provides comprehensive documentation for the DXT specification and architecture.
        * Contains detailed packaging instructions for building the extension.
    * **`manifest.json`**:
        * Defines the extension manifest with metadata including name, version, description, and author information.
        * Specifies the server configuration using Node.js with mcp-remote proxy.
        * Lists all available tools with their names and descriptions for Claude Desktop integration.
        * Includes keywords, license, and repository information.

3. **`gpt/` (ChatGPT GPT Integration Package)**
    * This directory contains files required to create the "Blockscout X-Ray" GPT in ChatGPT that integrates with the Blockscout MCP server via REST API.
    * **`README.md`**:
        * Provides comprehensive documentation for GPT creation and configuration.
        * Includes maintenance instructions and known issues with GPT behavior.
        * Specifies recommended GPT configuration (GPT-5 model, web search, code interpreter).
    * **`instructions.md`**:
        * Contains the core instructions for the GPT built following OpenAI GPT-5 prompting guide recommendations.
        * Incorporates content from the `__unlock_blockchain_analysis__` tool for enhanced reasoning.
        * Must be updated if the `__unlock_blockchain_analysis__` tool output changes.
    * **`action_tool_descriptions.md`**:
        * Contains detailed descriptions of all MCP tools available to the GPT.
        * Required due to GPT's 8,000 character limit for instructions.
        * Must be maintained and updated whenever MCP tools are modified or new ones are created.
    * **`openapi.yaml`**:
        * OpenAPI 3.1.0 specification for REST API endpoints used by GPT actions.
        * Contains modified tool descriptions to comply with OpenAPI standards (under 300 characters).
        * Excludes the `__unlock_blockchain_analysis__` endpoint since its data is embedded in GPT instructions.
        * Includes parameter modifications for OpenAPI compliance, particularly for `read_contract` tool.

4. **`tests/` (Test Suite)**
    * This directory contains the complete test suite for the project, divided into two categories:
    * **`tests/tools/`**: Contains the comprehensive **unit test** suite. All external API calls are mocked, allowing these tests to run quickly and offline. Tool-specific tests live in dedicated modules under category folders (for example, `tests/tools/address_tools/test_get_address_info.py`), and shared utilities are covered by modules like `test_common.py`.
        * Each test file corresponds to a single MCP tool and provides comprehensive test coverage:
            * **Success scenarios**: Testing normal operation with valid inputs and API responses.
            * **Error handling**: Testing API errors, chain lookup failures, timeout errors, and invalid responses.
            * **Edge cases**: Testing empty responses, missing fields, malformed data, and boundary conditions.
            * **Progress tracking**: Verifying correct MCP progress reporting behavior for all tools.
            * **Parameter validation**: Testing optional parameters, pagination, and parameter combinations.
        * Uses `pytest` and `pytest-asyncio` for async testing with comprehensive mocking strategies.
        * All tests maintain full isolation using `unittest.mock.patch` to mock external API calls.
    * **`tests/integration/`**: Contains the **integration test** suite. These tests make real network calls and are divided into two categories:
        * **Helper-level tests** in `test_common_helpers.py` verify basic connectivity and API availability.
        * **Tool-level tests** live in domain-specific folders (for example, `tests/integration/address/`). Each `test_*_real.py`
          module exercises exactly one MCP tool to keep test contexts focused for coding agents.
      All integration tests are marked with `@pytest.mark.integration` and are excluded from the default test run.

5. **`blockscout_mcp_server/` (Main Python Package)**
    * **`__init__.py`**: Standard file to mark the directory as a Python package.
    * **`llms.txt`**: Machine-readable guidance file for AI crawlers.
    * **`__main__.py`**:
        * Serves as the entry point when the package is run as a script (`python -m blockscout_mcp_server`).
        * Imports the main execution function (e.g., `run_server()`) from `server.py` and calls it.
    * **`models.py`**:
        * Defines a standardized, structured `ToolResponse` model using Pydantic.
        * Ensures all tools return data in a consistent, machine-readable format, separating the data payload from metadata like pagination and notes.
        * Includes specific data models for complex payloads, like the response from `__unlock_blockchain_analysis__`.
    * **`server.py`**:
        * The heart of the MCP server.
        * Initializes a `FastMCP` instance using constants from `constants.py`.
        * Imports all tool functions from the modules in the `tools/` sub-package.
        * Registers each tool with the `FastMCP` instance using the `@mcp.tool()` decorator. This includes:
            * Tool name (if different from the function name).
            * Tool description (from the function's docstring or explicitly provided).
            * Argument type hints and descriptions (using `typing.Annotated` and `pydantic.Field` for descriptions), which `FastMCP` uses to generate the input schema.
        * Implements CLI argument parsing using `typer` with support for:
            * `--http`: Enable HTTP Streamable mode
            * `--http-host`: Host for HTTP server (default: 127.0.0.1)
            * `--http-port`: Port for HTTP server (default: 8000)
        * Defines `run_server_cli()` function that:
            * Parses CLI arguments and determines the mode (stdio or HTTP)
            * For stdio mode: calls `mcp.run()` for stdin/stdout communication
            * For HTTP mode: configures stateless HTTP with JSON responses and runs uvicorn server
    * **`templates/`**:
        * **`index.html`**: Landing page for the REST API.
    * **`config.py`**:
        * Defines a Pydantic `BaseSettings` class to manage server configuration.
        * Loads configuration values (e.g., API keys, timeouts, cache settings) from environment variables.
        * Provides a singleton configuration object that can be imported and used by other modules, especially by `tools/common.py` for API calls.
    * **`constants.py`**:
        * Defines centralized constants used throughout the application, including data truncation limits.
        * Contains server instructions and other configuration strings.
        * Ensures consistency between different parts of the application.
        * Used by both server.py and tools like `tools/initialization/unlock_blockchain_analysis.py` to maintain a single source of truth.
    * **`logging_utils.py`**:
        * Provides utilities for configuring production-ready logging.
        * Contains the `replace_rich_handlers_with_standard()` function that eliminates multi-line Rich formatting from MCP SDK logs.
    * **`analytics.py`**:
        * Centralized Mixpanel analytics for MCP tool invocations.
        * Enabled only in HTTP mode when `BLOCKSCOUT_MIXPANEL_TOKEN` is set.
        * Generates deterministic `distinct_id` based on client IP, name, and version fingerprint.
        * Tracks tool invocations with client metadata, protocol version, and call source (MCP vs REST).
        * Includes IP geolocation metadata for Mixpanel and graceful error handling to avoid breaking tool execution.
    * **`telemetry.py`**:
        * Sends anonymous usage reports from self-hosted servers when direct analytics are disabled.
        * Designed as fire-and-forget and never disrupts tool execution.
    * **`client_meta.py`**:
        * Shared utilities for extracting client metadata (name, version, protocol, user_agent) from MCP Context.
        * Provides `ClientMeta` dataclass and `extract_client_meta_from_ctx()` function.
        * Falls back to User-Agent header when MCP client name is unavailable.
        * Ensures consistent sentinel defaults ("N/A", "Unknown") across logging and analytics modules.
    * **`cache.py`**:
        * Encapsulates in-memory caching of chain data with TTL management.
    * **`web3_pool.py`**:
        * Manages pooled `AsyncWeb3` instances with shared `aiohttp` sessions.
        * Provides a custom provider to ensure Blockscout RPC compatibility and connection reuse.
    * **`api/` (API layer)**:
        * **`helpers.py`**: Shared utilities for REST API handlers, including parameter extraction and error handling.
        * **`routes.py`**: Defines all REST API endpoints that wrap MCP tools.
        * **`dependencies.py`**: Dependency providers for the REST API, such as a mock context for stateless calls.
    * **`tools/` (Sub-package for Tool Implementations)**
        * **`__init__.py`**: Marks `tools` as a sub-package. May re-export tool functions for easier import into `server.py`.
        * **`common.py`**:
            * Provides shared utilities and common functionality for all MCP tools.
            * Handles API communication, chain resolution, pagination, data processing, and error handling.
            * Implements standardized patterns used across the tool ecosystem.
            * Includes logging helpers such as the `@log_tool_invocation` decorator.
        * **`decorators.py`**:
            * Contains the `log_tool_invocation` decorator and other logging helpers.
        * **Individual Tool Modules** (e.g., `address/get_address_info.py`, `transaction/get_transaction_info.py`):
            * Each MCP tool lives in its own module named after the tool function.
            * Modules are organized by domain (`address/`, `block/`, `contract/`, `transaction/`, etc.) to keep related tools together while preserving a 1:1 mapping.
            * Shared helpers used by multiple tools in the same domain live in `_shared.py` modules alongside the individual tool files.
            * Tool functions remain `async`, accept a `Context` argument for progress reporting, and use `typing.Annotated`/`pydantic.Field` for argument descriptions.
            * The function docstring provides the description surfaced to FastMCP clients.
            * Example modules:
                * `initialization/unlock_blockchain_analysis.py`: Implements `__unlock_blockchain_analysis__`, returning special server instructions and recommended chains.
                * `chains/get_chains_list.py`: Implements `get_chains_list`, returning a formatted list of blockchain chains with their IDs.
                * `ens/get_address_by_ens_name.py`: Implements `get_address_by_ens_name` via the BENS API.
                * `search/lookup_token_by_symbol.py`: Implements `lookup_token_by_symbol(chain_id, symbol)` with a strict result cap.
                * `contract/inspect_contract_code.py`: Uses helpers from `contract/_shared.py` to return metadata or source files for verified contracts.
                * `address/get_tokens_by_address.py`: Implements paginated ERC-20 holdings responses with `NextCallInfo` for follow-up requests.
                * `transaction/get_transactions_by_address.py`: Uses `_shared.py` helpers for smart pagination and filtering of advanced transactions.
