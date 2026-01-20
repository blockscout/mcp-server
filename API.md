# Blockscout MCP Server REST API

This document provides detailed documentation for the versioned REST API of the Blockscout MCP Server. This API offers a web-friendly, stateless interface to the same powerful blockchain tools available through the Model Context Protocol (MCP).

The base URL for all Version 1 endpoints is: `http://<host>:<port>/v1`

## Static Endpoints

These endpoints provide general information and are not part of the versioned API.

| Method | Path         | Description                                         |
| ------ | ------------ | --------------------------------------------------- |
| `GET`  | `/`          | Serves a static HTML landing page.                  |
| `GET`  | `/health`    | A simple health check endpoint. Returns `{"status": "ok"}`. |
| `GET`  | `/llms.txt`  | A machine-readable guidance file for AI crawlers.   |

## Authentication

The REST API is currently in an alpha stage and does not require authentication. This may be subject to change in future releases.

## General Concepts

### Standard Response Structure

All endpoints under `/v1/` return a consistent JSON object that wraps the tool's output. This structure, known as a `ToolResponse`, separates the primary data from important metadata.

```json
{
  "data": { ... },
  "data_description": [ ... ],
  "notes": [ ... ],
  "instructions": [ ... ],
  "pagination": { ... }
}
```

- `data`: The main data payload of the response. Its structure is specific to each endpoint.
- `data_description`: (Optional) A list of strings explaining the structure or fields of the `data` payload.
- `notes`: (Optional) A list of important warnings or contextual notes, such as data truncation alerts.
- `instructions`: (Optional) A list of suggested follow-up actions for an AI agent.
- `pagination`: (Optional) An object containing information to retrieve the next page of results.

### Error Handling

All error responses, regardless of the HTTP status code, return a JSON object with a consistent structure.

#### Error Response Structure

```json
{
  "error": "A descriptive error message"
}
```

#### Error Categories

- **Client-Side Errors (`4xx` status codes)**: These errors indicate a problem with the request itself. Common examples include:
  - **Validation Errors (`400 Bad Request`)**: Occur when a required parameter is missing or a parameter value is invalid.
  - **Deprecated Endpoints (`410 Gone`)**: Occur when a requested endpoint is no longer supported.

- **Server-Side Errors (`5xx` status codes)**: These errors indicate a problem on the server or with a downstream service. Common examples include:
  - **Internal Errors (`500 Internal Server Error`)**: Occur when the server encounters an unexpected condition.
  - **Downstream Timeouts (`504 Gateway Timeout`)**: Occur when a request to an external service (like a Blockscout API) times out.
  - **Other Downstream Errors**: The server may also pass through other `4xx` or `5xx` status codes from downstream services.

### Pagination

For endpoints that return large datasets, the response will include a `pagination` object. To fetch the next page, you **must** use the `tool_name` and `params` from the `next_call` object to construct your next request. The `cursor` is an opaque string that contains all necessary information for the server.

**Example Pagination Object:**

```json
{
  "pagination": {
    "next_call": {
      "tool_name": "get_tokens_by_address",
      "params": {
        "chain_id": "1",
        "address": "0x...",
        "cursor": "eyJibG9ja19udW1iZXIiOjE4OTk5OTk5LCJpbmRleCI6NDJ9"
      }
    }
  }
}
```

---

## Safety & Limits

### Response Size Limits
To prevent system overload and context exhaustion, the `direct_api_call` endpoint enforces a maximum response size limit (default: 100,000 characters).

If you receive a `413 Payload Too Large` (or similar error) indicating the response is too large, you can bypass this check by adding the following header to your request:

```http
X-Blockscout-Allow-Large-Response: true
```

*Note: This bypass is only available for REST API calls. MCP calls (used by AI agents) strictly enforce the limit.*

---

## API Endpoints

### Tool Discovery

#### List All Tools (`list_tools`)

Retrieves a list of all available tools and their MCP schemas.

`GET /v1/tools`

### Parameters

*None*

### Example Request

```bash
curl "http://127.0.0.1:8000/v1/tools"
```

### General Tools

#### Unlock Blockchain Analysis (`__unlock_blockchain_analysis__`)

Provides custom instructions and operational guidance for using the server. This is a mandatory first step.

`GET /v1/unlock_blockchain_analysis`
`GET /v1/get_instructions` (legacy)

### Parameters

*None*

### Example Request

```bash
curl "http://127.0.0.1:8000/v1/unlock_blockchain_analysis"
```

#### Get Chains List (`get_chains_list`)

Returns a list of all known blockchain chains, including whether each is a testnet, its native currency, ecosystem, and the settlement layer chain ID when applicable.

`GET /v1/get_chains_list`

### Parameters

*None*

### Example Request

```bash
curl "http://127.0.0.1:8000/v1/get_chains_list"
```

### Block Tools

#### Get Block Number (`get_block_number`)

Retrieves the block number and timestamp for a specific date/time or the latest block.

`GET /v1/get_block_number`

### Parameters

| Name       | Type     | Required | Description                                                                                                   |
| ---------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                                                                                     |
| `datetime` | `string` | No       | The date and time (ISO 8601 format, e.g. 2025-05-22T23:00:00.00Z) to find the block for. If omitted, returns the latest block. |

### Example Request

```bash
curl "http://127.0.0.1:8000/v1/get_block_number?chain_id=1&datetime=2023-01-01T00:00:00Z"
```

### Deprecated

`GET /v1/get_latest_block` is deprecated but still supported for backward compatibility.

#### Get Block Info (`get_block_info`)

Returns detailed information for a specific block.

`GET /v1/get_block_info`

**Parameters**

| Name                   | Type      | Required | Description                                          |
| ---------------------- | --------- | -------- | ---------------------------------------------------- |
| `chain_id`             | `string`  | Yes      | The ID of the blockchain.                            |
| `number_or_hash`       | `string`  | Yes      | The block number or its hash.                        |
| `include_transactions` | `boolean` | No       | If true, includes a list of transaction hashes.      |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_block_info?chain_id=1&number_or_hash=19000000&include_transactions=true"
```

### Transaction Tools

#### Get Transaction Info (`get_transaction_info`)

Gets comprehensive information for a single transaction.

`GET /v1/get_transaction_info`

**Parameters**

| Name                | Type      | Required | Description                                      |
| ------------------- | --------- | -------- | ------------------------------------------------ |
| `chain_id`          | `string`  | Yes      | The ID of the blockchain.                        |
| `transaction_hash`  | `string`  | Yes      | The hash of the transaction.                     |
| `include_raw_input` | `boolean` | No       | If true, includes the raw transaction input data.|

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_transaction_info?chain_id=1&transaction_hash=0x...&include_raw_input=true"
```

#### Get Transaction Summary (`transaction_summary`)

Provides a human-readable summary of a transaction's purpose.

`GET /v1/transaction_summary`

**Parameters**

| Name               | Type     | Required | Description                  |
| ------------------ | -------- | -------- | ---------------------------- |
| `chain_id`         | `string` | Yes      | The ID of the blockchain.    |
| `transaction_hash` | `string` | Yes      | The hash of the transaction. |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/transaction_summary?chain_id=1&transaction_hash=0x..."
```

#### Get Transactions by Address (`get_transactions_by_address`)

Gets native currency transfers and contract interactions for an address.

`GET /v1/get_transactions_by_address`

**Parameters**

| Name       | Type     | Required | Description                                        |
| ---------- | -------- | -------- | -------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                          |
| `address`  | `string` | Yes      | The address to query.                              |
| `age_from` | `string` | No       | Start date and time (ISO 8601 format).             |
| `age_to`   | `string` | No       | End date and time (ISO 8601 format).               |
| `methods`  | `string` | No       | A method signature to filter by (e.g., `0x304e6ade`).|
| `cursor`   | `string` | No       | The cursor for pagination from a previous response.|

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_transactions_by_address?chain_id=1&address=0x...&age_from=2024-01-01T00:00:00Z"
```

#### Get Token Transfers by Address (`get_token_transfers_by_address`)

Returns ERC-20 token transfers for an address.

`GET /v1/get_token_transfers_by_address`

**Parameters**

| Name       | Type     | Required | Description                                        |
| ---------- | -------- | -------- | -------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                          |
| `address`  | `string` | Yes      | The address to query.                              |
| `age_from` | `string` | No       | Start date and time (ISO 8601 format).             |
| `age_to`   | `string` | No       | End date and time (ISO 8601 format).               |
| `token`    | `string` | No       | An ERC-20 token contract address to filter by.     |
| `cursor`   | `string` | No       | The cursor for pagination from a previous response.|

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_token_transfers_by_address?chain_id=1&address=0x...&token=0x..."
```

### Address Tools

#### Get Address Info (`get_address_info`)

Gets comprehensive information about an address, including balance and contract details.

`GET /v1/get_address_info`

**Parameters**

| Name       | Type     | Required | Description                  |
| ---------- | -------- | -------- | ---------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.    |
| `address`  | `string` | Yes      | The address to get info for. |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_address_info?chain_id=1&address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
```

#### Get Address Logs (Deprecated) (`get_address_logs`)

This endpoint is deprecated and always returns a static notice.

`GET /v1/get_address_logs`

**Parameters**

| Name       | Type     | Required | Description                                        |
| ---------- | -------- | -------- | -------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                          |
| `address`  | `string` | Yes      | The address that emitted the logs.                 |
| `cursor`   | `string` | No       | The cursor for pagination from a previous response.|

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_address_logs?chain_id=1&address=0xabc"
```

**Example Response**

```json
{
  "data": {"status": "deprecated"},
  "notes": [
    "This endpoint is deprecated and will be removed in a future version.",
    "Please use the recommended workflow: first, call `get_transactions_by_address` (which supports time filtering), and then use `direct_api_call` with `endpoint_path='/api/v2/transactions/{transaction_hash}/logs'` for each relevant transaction hash."
  ],
  "pagination": null,
  "instructions": null
}
```

### Token & NFT Tools

#### Get Tokens by Address (`get_tokens_by_address`)

Returns ERC-20 token holdings for an address.

`GET /v1/get_tokens_by_address`

**Parameters**

| Name       | Type     | Required | Description                                        |
| ---------- | -------- | -------- | -------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                          |
| `address`  | `string` | Yes      | The wallet address to query.                       |
| `cursor`   | `string` | No       | The cursor for pagination from a previous response.|

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_tokens_by_address?chain_id=1&address=0x..."
```

#### Get NFT Tokens by Address (`nft_tokens_by_address`)

Retrieves NFT tokens (ERC-721, etc.) owned by an address.

`GET /v1/nft_tokens_by_address`

**Parameters**

| Name       | Type     | Required | Description                                        |
| ---------- | -------- | -------- | -------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                          |
| `address`  | `string` | Yes      | The NFT owner's address.                           |
| `cursor`   | `string` | No       | The cursor for pagination from a previous response.|

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/nft_tokens_by_address?chain_id=1&address=0x..."
```

### Search Tools

#### Lookup Token by Symbol (`lookup_token_by_symbol`)

Searches for tokens by their symbol or name.

`GET /v1/lookup_token_by_symbol`

**Parameters**

| Name       | Type     | Required | Description                       |
| ---------- | -------- | -------- | --------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.         |
| `symbol`   | `string` | Yes      | The token symbol to search for.   |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/lookup_token_by_symbol?chain_id=1&symbol=WETH"
```

### Contract & Name Service Tools

#### Get Contract ABI (`get_contract_abi`)

Retrieves the Application Binary Interface (ABI) for a smart contract.

`GET /v1/get_contract_abi`

**Parameters**

| Name       | Type     | Required | Description                  |
| ---------- | -------- | -------- | ---------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.    |
| `address`  | `string` | Yes      | The smart contract address.  |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_contract_abi?chain_id=1&address=0x..."
```

#### Inspect Contract Code (`inspect_contract_code`)

Returns contract metadata or the content of a specific source file for a verified smart contract.

`GET /v1/inspect_contract_code`

**Parameters**

| Name       | Type     | Required | Description                                                                 |
| ---------- | -------- | -------- | --------------------------------------------------------------------------- |
| `chain_id` | `string` | Yes      | The ID of the blockchain.                                                   |
| `address`  | `string` | Yes      | The smart contract address.                                                 |
| `file_name`| `string` | No       | The name of the source file to fetch. Omit to retrieve metadata and file list. |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/inspect_contract_code?chain_id=1&address=0x..."
```

#### Get Address by ENS Name (`get_address_by_ens_name`)

Converts an ENS (Ethereum Name Service) name to its corresponding Ethereum address.

`GET /v1/get_address_by_ens_name`

**Parameters**

| Name   | Type     | Required | Description                |
| ------ | -------- | -------- | -------------------------- |
| `name` | `string` | Yes      | The ENS name to resolve.   |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/get_address_by_ens_name?name=vitalik.eth"
```

### Read Contract (`read_contract`)

Executes a read-only smart contract function and returns its result.

`GET /v1/read_contract`

**Parameters**

| Name           | Type     | Required | Description                                     |
| -------------- | -------- | -------- | ----------------------------------------------- |
| `chain_id`     | `string` | Yes      | The ID of the blockchain.                       |
| `address`      | `string` | Yes      | Smart contract address.                         |
| `abi`          | `string` | Yes      | JSON-encoded function ABI dictionary.           |
| `function_name`| `string` | Yes      | Name of the function to call.                   |
| `args`         | `string` | No       | JSON-encoded array of function arguments.       |
| `block`        | `string` | No       | Block identifier or number (`latest` by default). |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/read_contract?chain_id=1&address=0xdAC17F958D2ee523a2206206994597C13D831ec7&function_name=balanceOf&abi=%7B%22constant%22%3Atrue%2C%22inputs%22%3A%5B%7B%22name%22%3A%22_owner%22%2C%22type%22%3A%22address%22%7D%5D%2C%22name%22%3A%22balanceOf%22%2C%22outputs%22%3A%5B%7B%22name%22%3A%22balance%22%2C%22type%22%3A%22uint256%22%7D%5D%2C%22payable%22%3Afalse%2C%22stateMutability%22%3A%22view%22%2C%22type%22%3A%22function%22%7D&args=%5B%220xF977814e90dA44bFA03b6295A0616a897441aceC%22%5D"
```

### Direct API Call (`direct_api_call`)

Allows calling a curated raw Blockscout API endpoint for advanced or chain-specific data.

`GET /v1/direct_api_call`

**Parameters**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `chain_id` | `string` | Yes | The ID of the blockchain. |
| `endpoint_path` | `string` | Yes | The Blockscout API path to call (e.g., `/api/v2/stats`). |
| `query_params` | `object` | No | Additional query parameters forwarded to the Blockscout API. Use bracket syntax in the query string, e.g., `query_params[page]=1`. |
| `cursor` | `string` | No | The cursor for pagination from a previous response. |

**Example Request**

```bash
curl "http://127.0.0.1:8000/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/proxy/account-abstraction/operations&query_params[sender]=0x91f51371D33e4E50e838057E8045265372f8d448"
```

### Report Tool Usage (`report_tool_usage`)

Receive an anonymous tool usage report from a community-run server.

`POST /v1/report_tool_usage`

**Headers**

| Name | Required | Description |
| ---- | -------- | ----------- |
| `User-Agent` | Yes | Identifies the reporting server version. |
| `Content-Type` | Yes | Must be `application/json`. |

**Parameters**

| Name | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `tool_name` | `string` | Yes | Name of the tool being reported. |
| `tool_args` | `object` | Yes | Arguments provided to the tool. |
| `client_name` | `string` | Yes | Name of the MCP client invoking the tool. |
| `client_version` | `string` | Yes | Version of the MCP client. |
| `protocol_version` | `string` | Yes | Model Context Protocol version used. |

**Example Request**

```bash
curl -X POST "http://127.0.0.1:8000/v1/report_tool_usage" \\
  -H "User-Agent: BlockscoutMCP/0.11.0" \\
  -H "Content-Type: application/json" \\
  -d '{"tool_name": "get_block_number", "tool_args": {"chain_id": "1"}, "client_name": "test-client", "client_version": "1.2.3", "protocol_version": "2024-11-05"}'
```
