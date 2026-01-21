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

### Using Claude Connectors Directory - Recommended

The easiest way to use the Blockscout MCP server with Claude ( Claude Web, Claude Desktop and Claude Code) is through the official [Anthropic Connectors Directory](https://claude.com/connectors). This provides a native, managed installation experience with automatic updates.

#### Installation

##### Option 1: Direct Link

Visit [claude.com/connectors/blockscout](https://claude.com/connectors/blockscout) and click links in "Used in" section to install the Blockscout connector.

##### Option 2: Via Settings

1. Open Claude (Web or Desktop app)
2. Go to Settings > Connectors > Browse connectors
3. Search for "Blockscout"
4. Click "Connect" to install

> **Note:** Connectors require a paid Claude plan (Pro, Team, Max, or Enterprise).

### Claude Code Setup

To quickly install the Blockscout MCP server for use with Claude Code, run the following command in your terminal:

```sh
claude mcp add --transport http blockscout https://mcp.blockscout.com/mcp/
```

After running this command, Blockscout will be available as an MCP server in Claude Code, allowing you to access and analyze blockchain data directly from your coding environment.

### Cursor Setup

Use [this deeplink](https://cursor.com/en/install-mcp?name=blockscout&config=eyJ1cmwiOiJodHRwczovL21jcC5ibG9ja3Njb3V0LmNvbS9tY3AiLCJ0aW1lb3V0IjoxODAwMDB9) to install the Blockscout MCP server in Cursor.

### Gemini CLI Setup

1. Add the following configuration to your `~/.gemini/settings.json` file:

    ```json
    {
      "mcpServers": {
        "blockscout": {
          "httpUrl": "https://mcp.blockscout.com/mcp",
          "timeout": 180000
        }
      }
    }
    ```

2. For detailed Gemini CLI MCP server configuration instructions, see the [official documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md).

## Try Blockscout X-Ray GPT

Experience the power of the Blockscout MCP server through our showcase GPT: **[Blockscout X-Ray](https://chatgpt.com/g/g-68a7f315edf481918641bd0ed1e60f8b-blockscout-x-ray)**

This GPT demonstrates the full capabilities of the MCP server, providing intelligent blockchain analysis and insights. It's a great way to explore what's possible when AI agents have contextual access to blockchain data.

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
6. `inspect_contract_code(chain_id, address, file_name=None)` - Allows getting the source files of verified contracts.
7. `get_address_info(chain_id, address)` - Gets comprehensive information about an address including balance, ENS association, contract status, token details, and public tags.
8. `get_tokens_by_address(chain_id, address, cursor=None)` - Returns detailed ERC20 token holdings for an address with enriched metadata and market data.
9. `get_block_number(chain_id, [datetime])` - Retrieves the block number and timestamp for a specific date/time or the latest block.
10. `get_transactions_by_address(chain_id, address, age_from, age_to, methods, cursor=None)` - Gets transactions for an address within a specific time range with optional method filtering.
11. `get_token_transfers_by_address(chain_id, address, age_from, age_to, token, cursor=None)` - Returns ERC-20 token transfers for an address within a specific time range.
12. `transaction_summary(chain_id, hash)` - Provides human-readable transaction summaries using Blockscout Transaction Interpreter.
13. `nft_tokens_by_address(chain_id, address, cursor=None)` - Retrieves NFT tokens owned by an address, grouped by collection.
14. `get_block_info(chain_id, number_or_hash, include_transactions=False)` - Returns block information including timestamp, gas used, burnt fees, and transaction count. Can optionally include a list of transaction hashes.
15. `get_transaction_info(chain_id, hash, include_raw_input=False)` - Gets comprehensive transaction information with decoded input parameters and detailed token transfers.
16. `read_contract(chain_id, address, abi, function_name, args='[]', block='latest')` - Executes a read-only smart contract function and returns its result. The `abi` argument is a JSON object describing the specific function's signature.
17. `direct_api_call(chain_id, endpoint_path, query_params=None, cursor=None)` - Calls a curated raw Blockscout API endpoint for specialized or chain-specific data.

## Example Prompts for AI Agents

```plaintext
Is any approval set for OP token on Optimism chain by `zeaver.eth`?
```

```plaintext
Calculate the total gas fees paid on Ethereum by address `0xcafe...cafe` in May 2025.
```

```plaintext
Which 10 most recent logs were emitted by `0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7`
before `Nov 08 2024 04:21:35 AM (-06:00 UTC)`?
```

```plaintext
Tell me more about the transaction `0xf8a55721f7e2dcf85690aaf81519f7bc820bc58a878fa5f81b12aef5ccda0efb`
on Redstone rollup.
```

```plaintext
Is there any blacklisting functionality of USDT token on Arbitrum One?
```

```plaintext
What is the latest block on Gnosis Chain and who is the block minter?
Were any funds moved from this minter recently?
```

```plaintext
When the most recent reward distribution of Kinto token was made to the wallet
`0x7D467D99028199D99B1c91850C4dea0c82aDDF52` in Kinto chain?
```

```plaintext
Which methods of `0x1c479675ad559DC151F6Ec7ed3FbF8ceE79582B6` on the Ethereum 
mainnet could emit `SequencerBatchDelivered`?
```

```plaintext
What is the most recent executed cross-chain message sent from the Arbitrum Sepolia
rollup to the base layer?
```

## Development & Deployment

### Local Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/blockscout/mcp-server.git
cd mcp-server
uv pip install -e . # or `pip install -e .`
```

To customize the leading part of the `User-Agent` header used for RPC requests,
set the `BLOCKSCOUT_MCP_USER_AGENT` environment variable (defaults to
"Blockscout MCP"). The server version is appended automatically.

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
docker run --rm -p 8000:8000 ghcr.io/blockscout/mcp-server:latest python -m blockscout_mcp_server --http --http-host 0.0.0.0
```

With custom port:

```bash
docker run --rm -p 8080:8080 ghcr.io/blockscout/mcp-server:latest python -m blockscout_mcp_server --http --http-host 0.0.0.0 --http-port 8080
```

**HTTP Mode with REST API:**

To run with the REST API enabled:

```bash
docker run --rm -p 8000:8000 ghcr.io/blockscout/mcp-server:latest python -m blockscout_mcp_server --http --rest --http-host 0.0.0.0
```

**Note:** When running in HTTP mode with Docker, use `--http-host 0.0.0.0` to bind to all interfaces so the server is accessible from outside the container.

**Stdio Mode:** The default stdio mode is designed for use with MCP hosts/clients (like Claude Desktop, Cursor) and doesn't make sense to run directly with Docker without an MCP client managing the communication.

### Testing with Claude Desktop

Use MCP bundle to test the server with Claude Desktop.

1. Build the bundle as per instructions in [mcpb/README.md](mcpb/README.md).
2. Open Claude Desktop.
3. Double-click to open the `blockscout-mcp-dev.mcpb` file to automatically install the bundle.
4. Configure the Blockscout MCP Server URL when prompted (default: `http://127.0.0.1:8000/mcp`)

## Privacy and Anonymous Telemetry

To help us improve the Blockscout MCP Server, community-run instances of the server collect anonymous usage data by default. This helps us understand which tools are most popular and guides our development efforts.

**What we collect:**

- The name of the tool being called (e.g., `get_block_number`).
- The parameters provided to the tool.
- The version of the Blockscout MCP Server being used.

**What we DO NOT collect:**

- We do not collect any personal data, IP addresses (the central server uses the sender's IP for geolocation via Mixpanel and then discards it), secrets, or private keys.

### How to Opt-Out

You can disable this feature at any time by setting the following environment variable:

```bash
export BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY=true
```

## License

This project is primarily distributed under the terms of the MIT license. See [LICENSE](LICENSE) for details.
