"""Constants used throughout the Blockscout MCP Server."""

from blockscout_mcp_server import __version__

SERVER_VERSION = __version__

COMMUNITY_TELEMETRY_URL = "https://mcp.blockscout.com"
COMMUNITY_TELEMETRY_ENDPOINT = "/v1/report_tool_usage"

ERROR_HANDLING_RULES = """
If you receive an error "500 Internal Server Error" for any tool, retry calling this tool up to 3 times 
until successful.
"""

CHAIN_ID_RULES = """
All Blockscout API tools require a chain_id parameter:
- If the chain ID to be used in the tools is not clear, use the tool `get_chains_list` to get chain IDs 
of all known chains.
- If no chain is specified in the user's prompt, assume "Ethereum Mainnet" (chain_id: 1) as the default.
"""

PAGINATION_RULES = """
PAGINATION HANDLING: When any tool response includes a 'pagination' field, this means there are additional 
pages of data available. You MUST use the exact tool call provided in 'pagination.next_call' to fetch the 
next page. The 'pagination.next_call' contains the complete tool name and all required parameters (including 
the cursor) for the next page request.

If the user asks for comprehensive data or 'all' results, and you receive a paginated response, continue 
calling the pagination tool calls until you have gathered all available data or reached a reasonable limit.
"""

TIME_BASED_QUERY_RULES = """
TIME-BASED QUERIES: When users ask for blockchain data with time constraints (before/after/between 
specific dates), start with transaction-level tools that support time filtering (`get_transactions_by_address`, 
`get_token_transfers_by_address`) rather than trying to filter other data types directly. Use `age_from` and 
`age_to` parameters to filter transactions by time, then retrieve associated data (logs, token transfers, etc.) 
from those specific transactions.
"""

BINARY_SEARCH_RULES = """
BINARY SEARCH FOR HISTORICAL BLOCKCHAIN DATA: Never paginate for temporal boundaries. Use binary search 
with `age_from`/`age_to` parameters to efficiently locate specific time periods or events in blockchain history.

## Pattern:
```
get_transactions_by_address(age_from: START, age_to: MID)
├── Results found → search earlier half: [START, MID]  
└── No results → search later half: [MID, END]
```

## Example: First transaction for vitalik.eth
```
1. get_transactions_by_address(age_from: "2015-07-30", age_to: "2015-12-31") → ✓ 
2. get_transactions_by_address(age_from: "2015-07-30", age_to: "2015-09-12") → ✗
3. get_transactions_by_address(age_from: "2015-09-12", age_to: "2015-10-03") → ✓
4. get_transactions_by_address(age_from: "2015-09-27", age_to: "2015-09-30") → ✓ 
   Found: 2015-09-28T08:24:43Z
5. get_transactions_by_address(age_from: "2015-07-30", age_to: "2015-09-28T08:24:42") → ✗
   Confirmed: This is the first transaction.
```

**Result: 5 API calls instead of potentially hundreds of pagination calls.**
"""

PORTFOLIO_ANALYSIS_RULES = """
PORTFOLIO BALANCE ANALYSIS: When asked to analyze a portfolio, net worth, or total assets for any address, you
MUST check BOTH native-coin data AND ERC-20 token data. Call `get_address_info` (native coin) AND
`get_tokens_by_address` (ERC-20 holdings) before answering. When ranking or selecting top tokens by USD value,
you MUST include the native coin balance (from `get_address_info`) as a candidate alongside ERC-20 holdings.
Checking only one results in an incomplete and incorrect analysis.
"""

FUNDS_MOVEMENT_RULES = """
FUNDS MOVEMENT ANALYSIS: When asked about funds movement, recent transfers, or transaction activity for any
address, you MUST check BOTH native-coin transfers AND ERC-20 token transfers. Call
`get_transactions_by_address` (native coin transfers) AND `get_token_transfers_by_address` (ERC-20 transfers)
before answering. Do not assume that "transactions" implies native coin only. Checking only one results in an
incomplete and incorrect analysis.
"""

# IMPORTANT: When modifying this constant, also update:
# - gpt/instructions.md
# - tests/evals/GEMINI-evals.md
DATA_ORDERING_AND_RESUMPTION_RULES = """
DATA ORDERING AND ANCHOR RESUMPTION: Time-ordered tools (transactions, token transfers, logs) return items in
DESCENDING order (newest first). When resuming from an anchor item, use the anchor's block as the time boundary
and client-side filter.
Never skip the anchor's block.

Ordering Keys (DESC):
- get_transactions_by_address: (block_number, transaction_index, internal_transaction_index)
- get_token_transfers_by_address: (block_number, transaction_index, token_transfer_batch_index, token_transfer_index)
- direct_api_call (logs): (block_number, index)  # index is global within block

Resume Pattern:
• For EARLIER items: age_to=anchor_block_timestamp, keep where ordering_key < anchor_key
• For LATER items: age_from=anchor_block_timestamp, keep where ordering_key > anchor_key

Example: Found transfer at (block=1000, tx_idx=5, transfer_idx=3). To find earlier transfers:
  Query: age_to=timestamp_of_block_1000
  Filter: keep only (block<1000) OR (block=1000 AND tx_idx<5) OR (block=1000 AND tx_idx=5 AND transfer_idx<3)

Critical Notes:
- Always compare the COMPLETE ordering key, not just block_number.
- If the anchor is in the boundary block, filter within that block to avoid duplicates or gaps.
"""

DIRECT_API_CALL_RULES = """
ADVANCED API USAGE: For specialized or chain-specific data not covered by other tools,
you can use `direct_api_call`. This tool can call a curated list of raw Blockscout API endpoints.
"""

ALLOW_LARGE_RESPONSE_HEADER = "X-Blockscout-Allow-Large-Response"

# Curated list of endpoints for the direct_api_call tool
DIRECT_API_CALL_ENDPOINT_LIST = {
    "common": [
        {
            "group": "Stats",
            "endpoints": [
                {
                    "path": "/stats-service/api/v1/counters",
                    "description": (
                        "Get consolidated historical and recent-window counters—totals and 24h/30m rollups for "
                        "blockchain activity (transactions, accounts, contracts, verified contracts, ERC-4337 "
                        "user ops), plus average block time and fee aggregates"
                    ),
                },
                {
                    "path": "/api/v2/stats",
                    "description": (
                        "Get real-time network status and market context—current gas price tiers with last-update "
                        "and next-update timing, network utilization, today's transactions, average block time "
                        "'now', and coin price/market cap."
                    ),
                },
            ],
        },
        {
            "group": "User Operations",
            "endpoints": [
                {
                    "path": "/api/v2/proxy/account-abstraction/operations/{user_operation_hash}",
                    "description": "Get details for a specific User Operation by its hash.",
                }
            ],
        },
        {
            "group": "Transactions",
            "endpoints": [
                {
                    "path": "/api/v2/transactions/{transaction_hash}/logs",
                    "description": "Get event logs for a specific transaction by its hash.",
                },
            ],
        },
        {
            "group": "Tokens & NFTs",
            "endpoints": [
                {
                    "path": "/api/v2/tokens/{token_contract_address}/instances",
                    "description": "Get all NFT instances for a given token contract address.",
                },
                {
                    "path": "/api/v2/tokens/{token_contract_address}/holders",
                    "description": "Get a list of holders for a given token.",
                },
                {
                    "path": "/api/v2/tokens/{token_contract_address}/instances/{instance_id}",
                    "description": "Get details for a specific NFT instance.",
                },
                {
                    "path": "/api/v2/tokens/{token_contract_address}/instances/{instance_id}/transfers",
                    "description": "Get transfer history for a specific NFT instance.",
                },
            ],
        },
    ],
    "specific": [
        {
            "chain_family": "Ethereum Mainnet and Gnosis",
            "endpoints": [
                {
                    "path": "/api/v2/addresses/{account_address}/beacon/deposits",
                    "description": "Get Beacon Chain deposits for a specific address.",
                },
                {
                    "path": "/api/v2/blocks/{block_number}/beacon/deposits",
                    "description": "Get Beacon Chain deposits for a specific block.",
                },
                {
                    "path": "/api/v2/addresses/{account_address}/withdrawals",
                    "description": "Get Beacon Chain withdrawals for a specific address.",
                },
                {
                    "path": "/api/v2/blocks/{block_number}/withdrawals",
                    "description": "Get Beacon Chain withdrawals for a specific block.",
                },
            ],
        },
        {
            "chain_family": "Arbitrum",
            "endpoints": [
                {
                    "path": "/api/v2/main-page/arbitrum/batches/latest-number",
                    "description": "Get the latest committed batch number for Arbitrum.",
                },
                {
                    "path": "/api/v2/arbitrum/batches/{batch_number}",
                    "description": "Get information for a specific Arbitrum batch.",
                },
                {
                    "path": "/api/v2/arbitrum/messages/to-rollup",
                    "description": "Get L1 to L2 messages for Arbitrum.",
                },
                {
                    "path": "/api/v2/arbitrum/messages/from-rollup",
                    "description": "Get L2 to L1 messages for Arbitrum.",
                },
                {
                    "path": "/api/v2/arbitrum/messages/withdrawals/{transaction_hash}",
                    "description": "Get L2 to L1 messages for a specific transaction hash on Arbitrum.",
                },
            ],
        },
        {
            "chain_family": "Optimism",
            "endpoints": [
                {
                    "path": "/api/v2/optimism/batches",
                    "description": "Get the latest committed batches for Optimism.",
                },
                {
                    "path": "/api/v2/optimism/batches/{batch_number}",
                    "description": "Get information for a specific Optimism batch.",
                },
                {
                    "path": "/api/v2/optimism/games",
                    "description": "Get dispute games for Optimism.",
                },
                {
                    "path": "/api/v2/optimism/deposits",
                    "description": "Get L1 to L2 messages (deposits) for Optimism.",
                },
                {
                    "path": "/api/v2/optimism/withdrawals",
                    "description": "Get L2 to L1 messages (withdrawals) for Optimism.",
                },
            ],
        },
        {
            "chain_family": "Celo",
            "endpoints": [
                {
                    "path": "/api/v2/celo/epochs",
                    "description": "Get the latest finalized epochs for Celo.",
                },
                {
                    "path": "/api/v2/celo/epochs/{epoch_number}",
                    "description": "Get information for a specific Celo epoch.",
                },
                {
                    "path": "/api/v2/celo/epochs/{epoch_number}/election-rewards/group",
                    "description": "Get validator group rewards for a specific Celo epoch.",
                },
                {
                    "path": "/api/v2/celo/epochs/{epoch_number}/election-rewards/validator",
                    "description": "Get validator rewards for a specific Celo epoch.",
                },
                {
                    "path": "/api/v2/celo/epochs/{epoch_number}/election-rewards/voter",
                    "description": "Get voter rewards for a specific Celo epoch.",
                },
            ],
        },
        {
            "chain_family": "zkSync",
            "endpoints": [
                {
                    "path": "/api/v2/main-page/zksync/batches/latest-number",
                    "description": "Get the latest committed batch number for zkSync.",
                },
                {
                    "path": "/api/v2/zksync/batches/{batch_number}",
                    "description": "Get information for a specific zkSync batch.",
                },
            ],
        },
        {
            "chain_family": "zkEVM",
            "endpoints": [
                {
                    "path": "/api/v2/zkevm/batches/confirmed",
                    "description": "Get the latest confirmed batches for zkEVM.",
                },
                {
                    "path": "/api/v2/zkevm/batches/{batch_number}",
                    "description": "Get information for a specific zkEVM batch.",
                },
                {
                    "path": "/api/v2/zkevm/deposits",
                    "description": "Get deposits for zkEVM.",
                },
                {
                    "path": "/api/v2/zkevm/withdrawals",
                    "description": "Get withdrawals for zkEVM.",
                },
            ],
        },
        {
            "chain_family": "Scroll",
            "endpoints": [
                {
                    "path": "/api/v2/scroll/batches",
                    "description": "Get the latest committed batches for Scroll.",
                },
                {
                    "path": "/api/v2/scroll/batches/{batch_number}",
                    "description": "Get information for a specific Scroll batch.",
                },
                {
                    "path": "/api/v2/blocks/scroll-batch/{batch_number}",
                    "description": "Get blocks for a specific Scroll batch.",
                },
                {
                    "path": "/api/v2/scroll/deposits",
                    "description": "Get L1 to L2 messages (deposits) for Scroll.",
                },
                {
                    "path": "/api/v2/scroll/withdrawals",
                    "description": "Get L2 to L1 messages (withdrawals) for Scroll.",
                },
            ],
        },
        {
            "chain_family": "Shibarium",
            "endpoints": [
                {
                    "path": "/api/v2/shibarium/deposits",
                    "description": "Get L1 to L2 messages (deposits) for Shibarium.",
                },
                {
                    "path": "/api/v2/shibarium/withdrawals",
                    "description": "Get L2 to L1 messages (withdrawals) for Shibarium.",
                },
            ],
        },
        {
            "chain_family": "Stability",
            "endpoints": [
                {
                    "path": "/api/v2/validators/stability",
                    "description": "Get the list of validators for Stability.",
                }
            ],
        },
        {
            "chain_family": "Zilliqa",
            "endpoints": [
                {
                    "path": "/api/v2/validators/zilliqa",
                    "description": "Get the list of validators for Zilliqa.",
                },
                {
                    "path": "/api/v2/validators/zilliqa/{validator_public_key}",
                    "description": "Get information for a specific Zilliqa validator.",
                },
            ],
        },
        {
            "chain_family": "Redstone",
            "endpoints": [
                {
                    "path": "/api/v2/mud/worlds",
                    "description": "Get a list of MUD worlds for Redstone.",
                },
                {
                    "path": "/api/v2/mud/worlds/{contract_address}/tables",
                    "description": "Get tables for a specific MUD world on Redstone.",
                },
                {
                    "path": "/api/v2/mud/worlds/{contract_address}/tables/{table_id}/records",
                    "description": "Get records for a specific MUD world table on Redstone.",
                },
                {
                    "path": "/api/v2/mud/worlds/{contract_address}/tables/{table_id}/records/{record_id}",
                    "description": "Get a specific record from a MUD world table on Redstone.",
                },
            ],
        },
    ],
}

RECOMMENDED_CHAINS = [
    {
        "name": "Ethereum",
        "chain_id": "1",
        "is_testnet": False,
        "native_currency": "ETH",
        "ecosystem": "Ethereum",
        "settlement_layer_chain_id": None,
    },
    {
        "name": "Polygon PoS",
        "chain_id": "137",
        "is_testnet": False,
        "native_currency": "POL",
        "ecosystem": "Polygon",
        "settlement_layer_chain_id": None,
    },
    {
        "name": "Base",
        "chain_id": "8453",
        "is_testnet": False,
        "native_currency": "ETH",
        "ecosystem": ["Ethereum", "Superchain"],
        "settlement_layer_chain_id": "1",
    },
    {
        "name": "Arbitrum One Nitro",
        "chain_id": "42161",
        "is_testnet": False,
        "native_currency": "ETH",
        "ecosystem": "Arbitrum",
        "settlement_layer_chain_id": "1",
    },
    {
        "name": "OP Mainnet",
        "chain_id": "10",
        "is_testnet": False,
        "native_currency": "ETH",
        "ecosystem": ["Optimism", "Superchain"],
        "settlement_layer_chain_id": "1",
    },
    {
        "name": "ZkSync Era",
        "chain_id": "324",
        "is_testnet": False,
        "native_currency": "ETH",
        "ecosystem": "zkSync",
        "settlement_layer_chain_id": "1",
    },
    {
        "name": "Gnosis",
        "chain_id": "100",
        "is_testnet": False,
        "native_currency": "XDAI",
        "ecosystem": "Gnosis",
        "settlement_layer_chain_id": None,
    },
    {
        "name": "Celo",
        "chain_id": "42220",
        "is_testnet": False,
        "native_currency": "CELO",
        "ecosystem": "Ethereum",
        "settlement_layer_chain_id": None,
    },
    {
        "name": "Scroll",
        "chain_id": "534352",
        "is_testnet": False,
        "native_currency": "ETH",
        "ecosystem": "Ethereum",
        "settlement_layer_chain_id": "1",
    },
]

SERVER_NAME = "blockscout-mcp-server"
DEFAULT_HTTP_PORT = 8000

# The maximum length for a log's `data` field before it's truncated.
# 514 = '0x' prefix + 512 hex characters (256 bytes).
LOG_DATA_TRUNCATION_LIMIT = 514

# The maximum length for a transaction's input data field before it's truncated.
# 514 = '0x' prefix + 512 hex characters (256 bytes).
INPUT_DATA_TRUNCATION_LIMIT = 514
