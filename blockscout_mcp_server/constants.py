# SPDX-License-Identifier: LicenseRef-Blockscout
"""Constants used throughout the Blockscout MCP Server."""

from blockscout_mcp_server import __version__

SERVER_VERSION = __version__

SKILL_POINTER_TEXT = (
    "Operating rules, execution strategies, and the curated `direct_api_call` endpoint reference "
    "for analyzing Blockscout data live in the `blockscout-analysis` skill. Consult the skill "
    "(and its bundled references) before invoking any other Blockscout MCP tool."
)

COMMUNITY_TELEMETRY_URL = "https://mcp.blockscout.com"
COMMUNITY_TELEMETRY_ENDPOINT = "/v1/report_tool_usage"

ALLOW_LARGE_RESPONSE_HEADER = "X-Blockscout-Allow-Large-Response"

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

TOOL_INVOCATION_STATUSES = {
    "__unlock_blockchain_analysis__": {
        "invoking": "Initializing blockchain analysis...",
        "invoked": "Blockchain analysis ready",
    },
    "get_block_info": {
        "invoking": "Fetching block information...",
        "invoked": "Block information ready",
    },
    "get_block_number": {
        "invoking": "Fetching latest block number...",
        "invoked": "Block number ready",
    },
    "get_address_by_ens_name": {
        "invoking": "Resolving ENS name...",
        "invoked": "ENS name resolved",
    },
    "get_transactions_by_address": {
        "invoking": "Fetching transactions...",
        "invoked": "Transactions ready",
    },
    "get_token_transfers_by_address": {
        "invoking": "Fetching token transfers...",
        "invoked": "Token transfers ready",
    },
    "lookup_token_by_symbol": {
        "invoking": "Looking up token by symbol...",
        "invoked": "Token lookup ready",
    },
    "get_contract_abi": {
        "invoking": "Fetching contract ABI...",
        "invoked": "Contract ABI ready",
    },
    "inspect_contract_code": {
        "invoking": "Inspecting contract code...",
        "invoked": "Contract code ready",
    },
    "read_contract": {
        "invoking": "Reading from contract...",
        "invoked": "Contract read complete",
    },
    "get_address_info": {
        "invoking": "Fetching address information...",
        "invoked": "Address information ready",
    },
    "get_tokens_by_address": {
        "invoking": "Fetching tokens by address...",
        "invoked": "Tokens ready",
    },
    "nft_tokens_by_address": {
        "invoking": "Fetching NFT tokens...",
        "invoked": "NFT tokens ready",
    },
    "get_transaction_info": {
        "invoking": "Fetching transaction details...",
        "invoked": "Transaction details ready",
    },
    "get_chains_list": {
        "invoking": "Fetching chains list...",
        "invoked": "Chains list ready",
    },
    "direct_api_call": {
        "invoking": "Calling Blockscout API...",
        "invoked": "API call complete",
    },
}

SERVER_NAME = "blockscout-mcp-server"
DEFAULT_HTTP_PORT = 8000

# The maximum length for a log's `data` field before it's truncated.
# 514 = '0x' prefix + 512 hex characters (256 bytes).
LOG_DATA_TRUNCATION_LIMIT = 514

# The maximum length for a transaction's input data field before it's truncated.
# 514 = '0x' prefix + 512 hex characters (256 bytes).
INPUT_DATA_TRUNCATION_LIMIT = 514
