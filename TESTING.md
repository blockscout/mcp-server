# Testing the Blockscout MCP Server

This project employs a two-tiered testing strategy to ensure both code correctness and reliable integration with external services:

1. **Unit Tests:** These are fast, offline tests that verify the internal logic of each tool. They use mocking to simulate API responses and ensure our code behaves as expected in isolation. They are meant to be run frequently during development.
2. **Integration Tests:** These are slower, online tests that make real network calls to live Blockscout APIs. Their purpose is to verify that our integration with these external services is still valid and to catch any breaking changes in the APIs themselves.

This document provides instructions for running both types of automated tests, as well as for performing manual end-to-end testing.

## Unit Testing

The project includes a comprehensive unit test suite covering all 16 MCP tool functions with 67 test cases across 10 test modules.

### Prerequisites for Unit Testing

- Python 3.10+ with the project installed in development mode
- Test dependencies installed: `pip install -e ".[test]"`
  - This includes `pytest`, `pytest-asyncio`, and `pytest-cov` for coverage reporting

### Mocking Strategy

The unit tests are designed to run quickly and reliably in any environment, including CI/CD pipelines, without any network access. To achieve this, the test suite uses a technique called **mocking**.

Instead of making real HTTP requests to external APIs (like Blockscout), the helper functions that make these calls are replaced with "mocks" using `unittest.mock`. These mocks are objects that can be controlled completely in tests. This approach provides several benefits:

- **Tool Isolation:** The logic of each tool function is tested in isolation from external services.
- **Scenario Simulation:** Mock APIs can be forced to return any response, including success data, empty lists, or error codes, allowing comprehensive testing of how tools handle every possibility.
- **Speed and Reliability:** Tests run in milliseconds without being affected by network latency or API downtime.

### Running Unit Tests

**Run all tests:**

```bash
pytest
```

**Run tests with verbose output:**

```bash
pytest -v
```

**Run tests for a specific module:**

```bash
pytest tests/tools/test_address_tools.py -v
```

**Run tests with coverage report:**

```bash
pytest --cov=blockscout_mcp_server --cov-report=html
```

### Test Structure

The unit tests are organized as follows:

- **`tests/tools/`**: Contains test modules for each tool implementation
- **Test Categories**: Success scenarios, error handling, edge cases, progress tracking, parameter validation
- **Mocking Strategy**: All external API calls are mocked using `unittest.mock.patch` for isolation
- **Execution Speed**: All tests complete in under 1 second with full isolation

### Key Testing Patterns

- **Simple Tools**: Basic API calls with straightforward data processing
- **Parameterized Tools**: Tools with optional parameters and complex input validation
- **Complex Logic**: Tools with pagination, data transformation, and string formatting
- **Wrapper Integration**: Tools using periodic progress wrappers for long-running operations

## Integration Testing

The project also includes a suite of integration tests that verify live connectivity and API contracts with external services like Chainscout, BENS, and Blockscout instances.

### How it Works

- **Real Network Calls:** Unlike unit tests, these tests require an active internet connection.
- **`@pytest.mark.integration`:** Each integration test is marked with a custom `pytest` marker, allowing them to be run separately from unit tests.
- **Excluded by Default:** To keep the default test run fast and offline-friendly, integration tests are **excluded** by default (as configured in `pytest.ini`).

### Running Integration Tests

To run **only** the integration tests, use the `-m` flag to select the `integration` marker:

```bash
pytest -m integration -v
```

**Important:** Always use the `-v` (verbose) flag when running integration tests to see the reason for any skipped tests.

This verbose output will show you why specific tests were skipped (e.g., network connectivity issues, missing API keys, or external service unavailability), which is crucial for understanding the test results.

This command is useful for periodically checking the health of our external dependencies or before deploying a new version.

## Manual End-to-End Testing

### Prerequisites for HTTP Testing

- Docker or local Python environment with the server installed
- `curl` command-line tool

### Starting the Server

To test the REST API, you must start the server with both the `--http` and `--rest` flags.

**Using Local Installation:**
```bash
python -m blockscout_mcp_server --http --rest --http-port 8000
```

**Using Docker:**
```bash
docker run --rm -p 8000:8000 ghcr.io/blockscout/mcp-server:latest --http --rest --http-host 0.0.0.0 --http-port 8000
```

The server will start and listen on `http://127.0.0.1:8000`.

### Testing MCP over HTTP

These examples show how to interact with the server using the native MCP JSON-RPC protocol over HTTP. The MCP endpoint is available at `/mcp/`. **Note**: The trailing slash is required.

#### 1. List Available Tools

```bash
curl --request POST \
  --url http://127.0.0.1:8000/mcp/ \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc": "2.0",
    "id": 0,
    "method": "tools/list"
  }'

This will return a list of all available tools with their descriptions and input schemas.

#### 2. Get Server Instructions

```bash
curl --request POST \
  --url http://127.0.0.1:8000/mcp/ \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "__get_instructions__",
      "arguments": {}
    }
  }'
```

#### 3. Get List of Supported Chains

```bash
curl --request POST \
  --url http://127.0.0.1:8000/mcp/ \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_chains_list",
      "arguments": {}
    }
  }'
```

#### Expected MCP Response Format

All MCP responses follow the JSON-RPC 2.0 format:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Tool result content here"
      }
    ],
    "isError": false
  }
}
```

### Testing the REST API

#### 1. Health Check
```bash
curl http://127.0.0.1:8000/health
```

#### 2. Get Latest Block (Success Case)
```bash
curl "http://127.0.0.1:8000/v1/get_latest_block?chain_id=1"
```

#### 3. Get Block Info (With Optional Parameter)
```bash
curl "http://127.0.0.1:8000/v1/get_block_info?chain_id=1&number_or_hash=19000000&include_transactions=true"
```

#### 4. Get Block Info (Error Case - Missing Required Parameter)
This request is missing the `number_or_hash` parameter and should return a 400 error.
```bash
curl -i "http://127.0.0.1:8000/v1/get_block_info?chain_id=1"
```


#### Expected REST API Response Format

All successful REST API responses return a `200 OK` status with a JSON body that follows the standard `ToolResponse` structure:

```json
{
  "data": { "...": "..." },
  "data_description": null,
  "notes": null,
  "instructions": null,
  "pagination": null
}
```

- `data`: The main data payload, specific to each endpoint.
- `data_description`, `notes`, `instructions`, `pagination`: Optional metadata fields that provide additional context.

Error responses will have a different structure as described in `API.md`.
