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
    (
        "PAGINATION HANDLING: When any tool response includes a 'pagination' field, "
        "this means there are additional pages of data available. "
        "You MUST use the exact tool call provided in 'pagination.next_call' to fetch the next page. "
        "The 'pagination.next_call' contains the complete tool name and all required parameters "
        "(including the cursor) for the next page request."
    ),
    (
        "If the user asks for comprehensive data or 'all' results, "
        "and you receive a paginated response, continue calling the pagination tool calls "
        "until you have gathered all available data or reached a reasonable limit."
    ),
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
# 514 = '0x' prefix + 512 hex characters (256 bytes).
LOG_DATA_TRUNCATION_LIMIT = 514

# The maximum length for a transaction's input data field before it's truncated.
# 514 = '0x' prefix + 512 hex characters (256 bytes).
INPUT_DATA_TRUNCATION_LIMIT = 514
