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
    (
        "TIME-BASED QUERIES: When users ask for blockchain data with time constraints "
        "(before/after/between specific dates), "
        "start with transaction-level tools that support time filtering (`get_transactions_by_address`, "
        "`get_token_transfers_by_address`) rather than trying to filter other data types directly. "
        "Use `age_from` and `age_to` parameters to filter transactions by time, "
        "then retrieve associated data (logs, token transfers, etc.) from those specific transactions."
    ),
    (
        "BLOCK TIME ESTIMATION: When no direct time filtering is available and you need to navigate "
        "to a specific time period, "
        "use mathematical block time estimation instead of brute-force iteration. "
        "For known chains, use established patterns "
        "(Ethereum ~12s, Polygon ~2s, Base ~2s, etc.). For unknown chains or improved accuracy, use adaptive sampling: "
        "1. Sample 2-3 widely-spaced blocks to calculate initial average block time "
        "2. Calculate approximate target: target_block ≈ current_block - "
        "(time_difference_in_seconds / average_block_time) "
        "3. As you gather new block data, refine your estimates using local patterns "
        "(detect if recent segments have different timing) "
        "4. Self-correct: if block 1800000→1700000 shows different timing than 1900000→1800000, "
        "use the more relevant local segment "
        "This adaptive approach works on any blockchain and automatically handles network upgrades or timing changes."
    ),
    (
        "EFFICIENCY OPTIMIZATION: When direct tools don't exist for your query, be creative and strategic: "
        "1. Assess the 'distance' - if you need data from far back in time, use block estimation first "
        "2. Avoid excessive iteration - if you find yourself making >5 sequential calls for timestamps, "
        "switch to estimation "
        "3. Use adaptive sampling - check a few data points to understand timing patterns, "
        "then adjust your strategy as you learn "
        "4. Learn continuously - refine your understanding of network patterns as new data becomes available "
        "5. Detect pattern changes - if your estimates become less accurate, "
        "recalibrate using more recent data segments "
        "6. Combine approaches - use estimation to get close, then fine-tune with iteration, "
        "always learning from each step"
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
