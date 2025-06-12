# Blockscout MCP Server

## Project Structure

```text
mcp-server/
├── blockscout_mcp_server/      # Main Python package for the server
│   ├── __init__.py             # Makes the directory a Python package
│   ├── __main__.py             # Entry point for `python -m blockscout_mcp_server`
│   ├── server.py               # Core server logic: FastMCP instance, tool registration, CLI
│   ├── config.py               # Configuration management (e.g., API keys, timeouts, cache settings)
│   ├── constants.py            # Centralized constants used throughout the application
│   └── tools/                  # Sub-package for tool implementations
│       ├── __init__.py         # Initializes the tools sub-package
│       ├── common.py           # Shared utilities for tools (e.g., HTTP client, chain resolution)
│       ├── get_instructions.py # Implements the __get_instructions__ tool
│       ├── ens_tools.py        # Implements ENS-related tools
│       ├── search_tools.py     # Implements search-related tools (e.g., lookup_token_by_symbol)
│       ├── contract_tools.py   # Implements contract-related tools (e.g., get_contract_abi)
│       ├── address_tools.py    # Implements address-related tools (e.g., get_address_info, get_tokens_by_address, get_address_logs)
│       ├── block_tools.py      # Implements block-related tools (e.g., get_latest_block, get_block_info)
│       ├── transaction_tools.py# Implements transaction-related tools (e.g., get_transactions_by_address, transaction_summary)
│       └── chains_tools.py     # Implements chain-related tools (e.g., get_chains_list)
├── tests/                      # Test suite for all MCP tools
│   ├── integration/            # Integration tests that make real network calls
│   │   ├── __init__.py         # Marks integration as a sub-package
│   │   ├── test_address_tools_integration.py   # Tool-level integration tests for address tools
│   │   ├── test_block_tools_integration.py     # Tool-level integration tests for block tools
│   │   ├── test_chains_tools_integration.py    # Tool-level integration tests for chains tools
│   │   ├── test_common_helpers.py              # Helper-level integration tests for API helpers
│   │   ├── test_contract_tools_integration.py  # Tool-level integration tests for contract tools
│   │   ├── test_ens_tools_integration.py       # Tool-level integration tests for ENS tools
│   │   ├── test_search_tools_integration.py    # Tool-level integration tests for search tools
│   │   └── test_transaction_tools_integration.py # Tool-level integration tests for transaction tools
│   └── tools/                  # Unit test modules for each tool implementation
│       ├── test_common.py            # Tests for shared utility functions
│       ├── test_address_tools.py     # Tests for address-related tools (get_address_info, get_tokens_by_address)
│       ├── test_address_tools_2.py   # Extended tests for complex address tools (nft_tokens_by_address, get_address_logs)
│       ├── test_block_tools.py       # Tests for block-related tools (get_latest_block, get_block_info)
│       ├── test_chains_tools.py      # Tests for chain-related tools (get_chains_list)
│       ├── test_contract_tools.py    # Tests for contract-related tools (get_contract_abi)
│       ├── test_ens_tools.py         # Tests for ENS-related tools (get_address_by_ens_name)
│       ├── test_get_instructions.py  # Tests for instruction tool (__get_instructions__)
│       ├── test_search_tools.py      # Tests for search-related tools (lookup_token_by_symbol)
│       ├── test_transaction_tools.py # Tests for transaction tools (get_transactions_by_address, transaction_summary)
│       └── test_transaction_tools_2.py # Extended tests for transaction tools (get_transaction_info, get_transaction_logs)
├── Dockerfile                  # For building the Docker image
├── pytest.ini                  # Pytest configuration (excludes integration tests by default)
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
            * `BLOCKSCOUT_CHAINSCOUT_URL`: URL for the Chainscout API (for chain resolution).
            * `BLOCKSCOUT_CHAINSCOUT_TIMEOUT`: Timeout for Chainscout API requests.
            * `BLOCKSCOUT_CHAIN_CACHE_TTL_SECONDS`: Time-to-live for chain resolution cache.
            * `BLOCKSCOUT_PROGRESS_INTERVAL_SECONDS`: Interval for periodic progress updates in long-running operations.

2. **`tests/` (Test Suite)**
    * This directory contains the complete test suite for the project, divided into two categories:
    * **`tests/tools/`**: Contains the comprehensive **unit test** suite. All external API calls are mocked, allowing these tests to run quickly and offline. It includes tests for each tool module and for shared utilities in `test_common.py`.
        * Each test file corresponds to a tool module and provides comprehensive test coverage:
            * **Success scenarios**: Testing normal operation with valid inputs and API responses.
            * **Error handling**: Testing API errors, chain lookup failures, timeout errors, and invalid responses.
            * **Edge cases**: Testing empty responses, missing fields, malformed data, and boundary conditions.
            * **Progress tracking**: Verifying correct MCP progress reporting behavior for all tools.
            * **Parameter validation**: Testing optional parameters, pagination, and parameter combinations.
        * Uses `pytest` and `pytest-asyncio` for async testing with comprehensive mocking strategies.
        * All tests maintain full isolation using `unittest.mock.patch` to mock external API calls.
        * Test execution completes in under 1 second with 67 total test cases across 10 test modules.
        * Provides 100% coverage of all 16 MCP tool functions with multiple test scenarios each.
    * **`tests/integration/`**: Contains the **integration test** suite. These tests make real network calls and are divided into two categories:
        * **Helper-level tests** in `test_common_helpers.py` verify basic connectivity and API availability.
        * **Tool-level tests** in `test_*_integration.py` validate that our tools extract and structure data correctly from live responses.
      All integration tests are marked with `@pytest.mark.integration` and are excluded from the default test run.

3. **`blockscout_mcp_server/` (Main Python Package)**
    * **`__init__.py`**: Standard file to mark the directory as a Python package.
    * **`__main__.py`**:
        * Serves as the entry point when the package is run as a script (`python -m blockscout_mcp_server`).
        * Imports the main execution function (e.g., `run_server()`) from `server.py` and calls it.
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
    * **`config.py`**:
        * Defines a Pydantic `BaseSettings` class to manage server configuration.
        * Loads configuration values (e.g., API keys, timeouts, cache settings) from environment variables.
        * Provides a singleton configuration object that can be imported and used by other modules, especially by `tools/common.py` for API calls.
    * **`constants.py`**:
        * Defines centralized constants used throughout the application.
        * Contains server instructions and other configuration strings.
        * Ensures consistency between different parts of the application.
        * Used by both server.py and tools like get_instructions.py to maintain a single source of truth.
    * **`tools/` (Sub-package for Tool Implementations)**
        * **`__init__.py`**: Marks `tools` as a sub-package. May re-export tool functions for easier import into `server.py`.
        * **`common.py`**:
            * Contains shared utility functions for all tool modules.
            * Implements chain resolution and caching mechanism with `get_blockscout_base_url` function.
            * Implements helper functions (`encode_cursor`, `decode_cursor`) and a custom exception (`InvalidCursorError`) for handling opaque pagination cursors.
            * Contains asynchronous HTTP client functions for different API endpoints:
                * `make_blockscout_request`: Takes base_url (resolved from chain_id), API path, and parameters for Blockscout API calls.
                * `make_bens_request`: For BENS API calls.
                * `make_chainscout_request`: For Chainscout API calls.
            * These functions handle:
                * API key inclusion
                * Common HTTP error patterns
                * URL construction
                * Response parsing
        * **Individual Tool Modules** (e.g., `ens_tools.py`, `transaction_tools.py`):
            * Each file will group logically related tools.
            * Each tool will be implemented as an `async` Python function.
            * For Blockscout API tools, functions take `chain_id` as the first parameter followed by other arguments and a `ctx: Context` parameter for progress tracking.
            * For fixed endpoint tools (like BENS), functions take only the required operation-specific parameters plus the `ctx: Context` parameter.
            * Argument descriptions are provided using `typing.Annotated[str, Field(description="...")]`.
            * The function's docstring serves as the tool's description for `FastMCP`.
            * All tools support MCP progress notifications, reporting progress at key steps (chain resolution, API calls, etc.).
            * Inside each Blockscout API tool function:
                1. It uses `get_blockscout_base_url(chain_id)` to dynamically resolve the appropriate Blockscout instance URL.
                2. It calls `make_blockscout_request` with the resolved base URL, API path, and query parameters.
                3. It processes the JSON response from Blockscout.
                4. It transforms this response into the desired output format.
                    * If the original `responseTemplate` was `{{.}}`, the function returns the parsed JSON (as a Python dict/list).
                    * If the original `responseTemplate` was custom, the function constructs the corresponding Python dictionary.
                    * If the original `responseTemplate` involved complex string formatting, the function constructs and returns the final response string.
                    * For paginated responses, it includes the chain_id in the pagination hint.
            * Examples:
                * `get_instructions.py`: Implements `__get_instructions__`, returning a pre-defined multi-line string with instructions and popular chain IDs.
                * `chains_tools.py`: Implements `get_chains_list`, returning a formatted list of blockchain chains with their IDs.
                * `ens_tools.py`: Implements `get_address_by_ens_name` (fixed BENS endpoint, no chain_id).
                * `search_tools.py`: Implements `lookup_token_by_symbol(chain_id, symbol)`.
                * `contract_tools.py`: Implements `get_contract_abi(chain_id, address)`.
                * `address_tools.py`: Implements `get_address_info(chain_id, address)` (includes public tags), `get_tokens_by_address(chain_id, address, cursor=None)`, `get_address_logs(chain_id, address, cursor=None)` with robust, cursor-based pagination.
                * `block_tools.py`: Implements `get_block_info(chain_id, number_or_hash, include_transactions=False)`, `get_latest_block(chain_id)`.
                * `transaction_tools.py`: Implements `get_transactions_by_address(chain_id, address, ...)`, `transaction_summary(chain_id, hash)`, etc.
