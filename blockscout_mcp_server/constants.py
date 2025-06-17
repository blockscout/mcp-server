"""
Constants used throughout the Blockscout MCP Server.
"""

SERVER_INSTRUCTIONS = """
Blockscout MCP server version: 0.3.1

If you receive an error "500 Internal Server Error" for any tool, retry calling this tool up to 3 times until successful.

All Blockscout API tools require a chain_id parameter:
- If the chain ID to be used in the tools is not clear, use the tool `get_chains_list` to get chain IDs of all known chains.
- If no chain is specified in the user's prompt, assume "Ethereum Mainnet" (chain_id: 1) as the default.
- Here is the list of IDs of most popular chains:
  * Ethereum: 1
  * Polygon PoS: 137
  * Base: 8453
  * Arbitrum One: 42161
  * OP Mainnet: 10
  * ZkSync Era: 324
  * Polygon zkEVM: 1101
  * Gnosis: 100
  * Celo: 42220
  * Scroll: 534352
"""

SERVER_NAME = "blockscout-mcp-server"

# The maximum length for a log's `data` field before it's truncated.
# 1026 = '0x' prefix + 1024 hex characters (512 bytes).
LOG_DATA_TRUNCATION_LIMIT = 1026
