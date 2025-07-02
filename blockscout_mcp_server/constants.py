"""Constants used throughout the Blockscout MCP Server."""

from blockscout_mcp_server import __version__

SERVER_VERSION = __version__

GENERAL_RULES = [
    (
        'If you receive an error "500 Internal Server Error" for any tool, '
        "retry calling this tool up to 3 times until successful."
    ),
    "All Blockscout API tools require a chain_id parameter:",
    (
        "If the chain ID to be used in the tools is not clear, use the tool "
        "`get_chains_list` to get chain IDs of all known chains."
    ),
    'If no chain is specified in the user\'s prompt, assume "Ethereum Mainnet" (chain_id: 1) as the default.',
]

RECOMMENDED_CHAINS = [
    {"name": "Ethereum", "chain_id": "1"},
    {"name": "Polygon PoS", "chain_id": "137"},
    {"name": "Base", "chain_id": "8453"},
    {"name": "Arbitrum One", "chain_id": "42161"},
    {"name": "OP Mainnet", "chain_id": "10"},
    {"name": "ZkSync Era", "chain_id": "324"},
    {"name": "Polygon zkEVM", "chain_id": "1101"},
    {"name": "Gnosis", "chain_id": "100"},
    {"name": "Celo", "chain_id": "42220"},
    {"name": "Scroll", "chain_id": "534352"},
]

SERVER_NAME = "blockscout-mcp-server"

# The maximum length for a log's `data` field before it's truncated.
# 1026 = '0x' prefix + 1024 hex characters (512 bytes).
LOG_DATA_TRUNCATION_LIMIT = 1026

# The maximum length for a transaction's input data field before it's truncated.
# 1026 = '0x' prefix + 1024 hex characters (512 bytes).
INPUT_DATA_TRUNCATION_LIMIT = 1026
