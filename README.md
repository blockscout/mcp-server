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
- **Versioned REST API**: Provides a standard, web-friendly interface to all MCP tools. See [API.md](API.md) for full documentation.
- Custom instructions for MCP host to use the server
- Intelligent context optimization to conserve LLM tokens while preserving data accessibility
- Smart response slicing with configurable page sizes to prevent context overflow
- Opaque cursor pagination using Base64URL-encoded strings instead of complex parameters
- Automatic truncation of large data fields with clear indicators and access guidance
- Standardized ToolResponse model with structured JSON responses and follow-up instructions
- Enhanced observability with MCP progress notifications and periodic updates for long-running operations

## Configuring MCP Clients

### Using the Claude Desktop Extension (.dxt) - Recommended

The easiest way to use the Blockscout MCP server with Claude Desktop is through the official Desktop Extension. This provides a seamless, one-click installation experience.

**Installation:**

1. Download the latest `blockscout-mcp.dxt` file from the [releases page](https://github.com/blockscout/mcp-server/releases)
2. Open Claude Desktop
3. Drag and drop the `.dxt` file directly into the Claude Desktop window
4. The extension will be automatically installed and ready to use

### Using the Official Blockscout MCP Server

The official cloud-hosted instance at `https://mcp.blockscout.com/mcp/` provides a reliable, always-updated service.

**Claude Desktop Setup:**

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
            "run",
            "--rm",
            "-i",
            "sparfenyuk/mcp-proxy:latest",
            "--transport",
            "streamablehttp",
            "https://mcp.blockscout.com/mcp/"
          ]
        }
      }
    }
    ```

5. Save the file and restart Claude Desktop
6. When chatting with Claude, you can now enable the Blockscout MCP Server to allow Claude to access blockchain data

**Cursor Setup:**

Use [this deeplink](cursor://anysphere.cursor-deeplink/mcp/install?name=blockscout&config=eyJ1cmwiOiJodHRwczovL21jcC5ibG9ja3Njb3V0LmNvbS9tY3AvIiwidGltZW91dCI6MTgwMDAwfQ%3D%3D) to install the Blockscout MCP server in Cursor.

**Gemini CLI Setup:**

1. Add the following configuration to your `~/.gemini/settings.json` file:

    ```json
    {
      "mcpServers": {
        "blockscout": {
          "httpUrl": "https://mcp.blockscout.com/mcp/",
          "timeout": 180000
        }
      }
    }
    ```

2. For detailed Gemini CLI MCP server configuration instructions, see the [official documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md).

### Local Development Setup (For Developers)

If you want to run the server locally for development purposes:

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

## Technical details

Refer to [SPEC.md](SPEC.md) for the technical details.

## Repository Structure

Refer to [AGENTS.md](AGENTS.md) for the repository structure.

## Testing

Refer to [TESTING.md](TESTING.md) for comprehensive instructions on running both **unit and integration tests**.

## Tool Descriptions

1. `__unlock_blockchain_analysis__()` - Provides custom instructions for the MCP host to use the server. This is a mandatory first step before using other tools.
2. `get_chains_list()` - Returns a list of all known chains.
3. `get_address_by_ens_name(name)` - Converts an ENS domain name to its corresponding Ethereum address.
4. `lookup_token_by_symbol(chain_id, symbol)` - Searches for token addresses by symbol or name, returning multiple potential matches.
5. `get_contract_abi(chain_id, address)` - Retrieves the ABI (Application Binary Interface) for a smart contract.
6. `get_address_info(chain_id, address)` - Gets comprehensive information about an address including balance, ENS association, contract status, token details, and public tags.
7. `get_tokens_by_address(chain_id, address, cursor=None)` - Returns detailed ERC20 token holdings for an address with enriched metadata and market data.
8. `get_latest_block(chain_id)` - Returns the latest indexed block number and timestamp.
9. `get_transactions_by_address(chain_id, address, age_from, age_to, methods, cursor=None)` - Gets transactions for an address within a specific time range with optional method filtering.
10. `get_token_transfers_by_address(chain_id, address, age_from, age_to, token, cursor=None)` - Returns ERC-20 token transfers for an address within a specific time range.
11. `transaction_summary(chain_id, hash)` - Provides human-readable transaction summaries using Blockscout Transaction Interpreter.
12. `nft_tokens_by_address(chain_id, address, cursor=None)` - Retrieves NFT tokens owned by an address, grouped by collection.
13. `get_block_info(chain_id, number_or_hash, include_transactions=False)` - Returns block information including timestamp, gas used, burnt fees, and transaction count. Can optionally include a list of transaction hashes.
14. `get_transaction_info(chain_id, hash, include_raw_input=False)` - Gets comprehensive transaction information with decoded input parameters and detailed token transfers.
15. `get_transaction_logs(chain_id, hash, cursor=None)` - Returns transaction logs with decoded event data.

## Example Prompts for AI Agents

```plaintext
On which popular networks is `ens.eth` deployed as a contract?
```

```plaintext
What are the usual activities performed by `ens.eth` on the Ethereum Mainnet?
Since it is a contract, what is the most used functionality of this contract?
Which address interacts with the contract the most?
```

```plaintext
Calculate the total gas fees paid on Ethereum by address `0xcafe...cafe` in May 2025.
```

```plaintext
Which 10 most recent logs were emitted by `0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7`
before `Nov 08 2024 04:21:35 AM (-06:00 UTC)`?
```

## Development & Deployment

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

**HTTP Mode (MCP only):**

To run the server in HTTP Streamable mode (stateless, JSON responses):

```bash
python -m blockscout_mcp_server --http
```

You can also specify the host and port for the HTTP server:

```bash
python -m blockscout_mcp_server --http --http-host 0.0.0.0 --http-port 8080
```

**HTTP Mode with REST API:**

To enable the versioned REST API alongside the MCP endpoint, use the `--rest` flag (which requires `--http`).

```bash
python -m blockscout_mcp_server --http --rest
```

With custom host and port:

```bash
python -m blockscout_mcp_server --http --rest --http-host 0.0.0.0 --http-port 8080
```

**CLI Options:**

- `--http`: Enables HTTP Streamable mode.
- `--http-host TEXT`: Host to bind the HTTP server to (default: `127.0.0.1`).
- `--http-port INTEGER`: Port for the HTTP server (default: `8000`).
- `--rest`: Enables the REST API (requires `--http`).

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

**HTTP Mode (MCP only):**

To run the Docker container in HTTP mode with port mapping:

```bash
docker run --rm -p 8000:8000 ghcr.io/blockscout/mcp-server:latest --http --http-host 0.0.0.0
```

With custom port:

```bash
docker run --rm -p 8080:8080 ghcr.io/blockscout/mcp-server:latest --http --http-host 0.0.0.0 --http-port 8080
```

**HTTP Mode with REST API:**

To run with the REST API enabled:

```bash
docker run --rm -p 8000:8000 ghcr.io/blockscout/mcp-server:latest --http --rest --http-host 0.0.0.0
```

**Note:** When running in HTTP mode with Docker, use `--http-host 0.0.0.0` to bind to all interfaces so the server is accessible from outside the container.

**Stdio Mode:** The default stdio mode is designed for use with MCP hosts/clients (like Claude Desktop, Cursor) and doesn't make sense to run directly with Docker without an MCP client managing the communication.

## License

This project is primarily distributed under the terms of the MIT license. See [LICENSE](LICENSE) for details.
