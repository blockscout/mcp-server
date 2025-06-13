# Blockscout MCP Server

[![smithery badge](https://smithery.ai/badge/@blockscout/mcp-server)](https://smithery.ai/server/@blockscout/mcp-server)

<a href="https://glama.ai/mcp/servers/@blockscout/mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@blockscout/mcp-server/badge" alt="Blockscout Server MCP server" />
</a>

The Model Context Protocol (MCP) is an open protocol designed to allow AI agents, IDEs, and automation tools to consume, query, and analyze structured data through context-aware APIs.

This server wraps Blockscout APIs and exposes blockchain data—balances, tokens, NFTs, contract metadata—via MCP so that AI agents and tools (like Claude, Cursor, or IDEs) can access and analyze it contextually.

**Key Features:**

- Contextual blockchain data access for AI tools
- Multi-chain support via getting Blockscout instance URLs from Chainscout
- Custom instructions for MCP host to use the server
- Supports MCP progress notifications for multi-step tool operations, allowing clients to track execution status
- Enhanced User Experience: Provides periodic progress updates for long-running API queries (e.g., fetching extensive transaction histories) when requested by the client, improving responsiveness

## Technical details

Refer to [SPEC.md](SPEC.md) for the technical details.

## Repository Structure

Refer to [AGENTS.md](AGENTS.md) for the repository structure.

## Testing

Refer to [TESTING.md](TESTING.md) for comprehensive instructions on running both **unit and integration tests**.

## Tool Descriptions

1. `__get_instructions__()` - Provides custom instructions for the MCP host to use the server. This tool is required since the field `instructions` of the MCP server initialization response is not used by the MCP host so far (tested on Claude Desktop).
2. `get_chains_list()` - Returns a list of all known chains.
3. `get_address_by_ens_name(name)` - Converts an ENS domain name to its corresponding Ethereum address.
4. `lookup_token_by_symbol(chain_id, symbol)` - Searches for token addresses by symbol or name, returning multiple potential matches.
5. `get_contract_abi(chain_id, address)` - Retrieves the ABI (Application Binary Interface) for a smart contract.
6. `get_address_info(chain_id, address)` - Gets comprehensive information about an address including balance, ENS association, contract status, token details, and public tags.
7. `get_tokens_by_address(chain_id, address, cursor=None)` - Returns detailed ERC20 token holdings for an address with enriched metadata and market data.
8. `get_latest_block(chain_id)` - Returns the latest indexed block number and timestamp.
9. `get_transactions_by_address(chain_id, address, age_from, age_to, methods)` - Gets transactions for an address within a specific time range with optional method filtering.
10. `get_token_transfers_by_address(chain_id, address, age_from, age_to, token)` - Returns ERC-20 token transfers for an address within a specific time range.
11. `transaction_summary(chain_id, hash)` - Provides human-readable transaction summaries using Blockscout Transaction Interpreter.
12. `nft_tokens_by_address(chain_id, address, cursor=None)` - Retrieves NFT tokens owned by an address, grouped by collection.
13. `get_block_info(chain_id, number_or_hash, include_transactions=False)` - Returns block information including timestamp, gas used, burnt fees, and transaction count. Can optionally include a list of transaction hashes.
14. `get_transaction_info(chain_id, hash, include_raw_input=False)` - Gets comprehensive transaction information with decoded input parameters and detailed token transfers.
15. `get_transaction_logs(chain_id, hash, cursor=None)` - Returns transaction logs with decoded event data.
16. `get_address_logs(chain_id, address, cursor=None)` - Gets logs emitted by a specific address with decoded event data.

## Example Prompts for AI Agents (to be added)

> _Placeholder_: Practical examples of prompts for chats or IDEs to retrieve and analyze blockchain data via the MCP server will be added in this section.

## Installation & Usage

### Local Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/blockscout/mcp-server.git
cd mcp-server
uv pip install -e . # or `pip install -e .`
```

### Running the Server

The server runs in `stdio` mode by default:

```bash
python -m blockscout_mcp_server
```

**HTTP Streamable Mode:**

To run the server in HTTP Streamable mode (stateless, JSON responses):

```bash
python -m blockscout_mcp_server --http
```

You can also specify the host and port for the HTTP server:

```bash
python -m blockscout_mcp_server --http --http-host 0.0.0.0 --http-port 8080
```

**CLI Options:**

- `--http`: Enables HTTP Streamable mode.
- `--http-host TEXT`: Host to bind the HTTP server to (default: `127.0.0.1`).
- `--http-port INTEGER`: Port for the HTTP server (default: `8000`).

### Building Docker Image Locally

Build the Docker image with the official tag:

```bash
docker build -t ghcr.io/blockscout/mcp-server:latest .
```

### Pulling from GitHub Container Registry

Pull the pre-built image:

```bash
docker pull ghcr.io/blockscout/mcp-server:latest
```

### Running with Docker

**HTTP Streamable Mode:**

To run the Docker container in HTTP mode with port mapping:

```bash
docker run --rm -p 8000:8000 ghcr.io/blockscout/mcp-server:latest python -m blockscout_mcp_server --http --http-host 0.0.0.0
```

With custom port:

```bash
docker run --rm -p 8080:8080 ghcr.io/blockscout/mcp-server:latest python -m blockscout_mcp_server --http --http-host 0.0.0.0 --http-port 8080
```

**Note:** When running in HTTP mode with Docker, use `--http-host 0.0.0.0` to bind to all interfaces so the server is accessible from outside the container.

**Stdio Mode:** The default stdio mode is designed for use with MCP hosts/clients (like Claude Desktop, Cursor) and doesn't make sense to run directly with Docker without an MCP client managing the communication.

### Configuring Claude Desktop

To use this MCP server with Claude Desktop:

1. Open Claude Desktop and click on Settings
2. Navigate to the "Developer" section
3. Click "Edit Config"
4. Open the file `claude_desktop_config.json` and configure the server:

    ```json
    {
      "mcpServers": {
        "blockscout": {
          "command": "docker",
          "args": [
            "run", "--rm", "-i",
            "ghcr.io/blockscout/mcp-server:latest"
          ]
        }
      }
    }
    ```

5. Save the file and restart Claude Desktop
6. When chatting with Claude, you can now enable the Blockscout MCP Server to allow Claude to access blockchain data

## License

This project is primarily distributed under the terms of the MIT license. See [LICENSE](LICENSE) for details.