# Testing the Blockscout MCP Server

This document provides instructions for testing the Blockscout MCP server locally using HTTP mode.

## Prerequisites

- Docker or local Python environment with the server installed
- `curl` command-line tool

## Starting the Server in HTTP Mode

### Using Docker

```bash
docker run --rm -p 8080:8080 ghcr.io/blockscout/mcp-server:latest python -m blockscout_mcp_server --http --http-host 0.0.0.0 --http-port 8080
```

### Using Local Installation

```bash
python -m blockscout_mcp_server --http --http-port 8080
```

The server will start and listen on `http://127.0.0.1:8080`.

## Testing with curl

### 1. List Available Tools

```bash
curl --request POST \
  --url http://127.0.0.1:8080/mcp/ \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc": "2.0",
    "id": 0,
    "method": "tools/list"
  }'
```

This will return a list of all available tools with their descriptions and input schemas.

### 2. Get Server Instructions

```bash
curl --request POST \
  --url http://127.0.0.1:8080/mcp/ \
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

### 3. Get List of Supported Chains

```bash
curl --request POST \
  --url http://127.0.0.1:8080/mcp/ \
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

### 4. Get Latest Block Information

```bash
curl --request POST \
  --url http://127.0.0.1:8080/mcp/ \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_latest_block",
      "arguments": {
        "chain_id": "1"
      }
    }
  }'
```

### 5. Get Address Information

```bash
curl --request POST \
  --url http://127.0.0.1:8080/mcp/ \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "get_address_info",
      "arguments": {
        "chain_id": "1",
        "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
      }
    }
  }'
```

## Expected Response Format

All responses follow the JSON-RPC 2.0 format:

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
