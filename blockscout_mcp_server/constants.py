# SPDX-License-Identifier: LicenseRef-Blockscout
"""Constants used throughout the Blockscout MCP Server."""

from typing import Literal

from blockscout_mcp_server import __version__

SERVER_VERSION = __version__

SKILL_POINTER_TEXT_TEMPLATE = (
    "Operating rules, execution strategies, and the curated `direct_api_call` endpoint reference "
    "for analyzing Blockscout data live in the `blockscout-analysis` skill{version_note}. If the skill is already "
    "loaded in your context, use that copy. If no copy is loaded, fetch the entry point from "
    "`blockscout-mcp://skill/SKILL.md` over MCP resources or `GET /skill/SKILL.md` over HTTP."
)

SKILL_RESOLUTION_RULE_TEXT = (
    "When `SKILL.md` mentions a reference path such as `references/foo.md`, resolve it as "
    "`blockscout-mcp://skill/` plus that path over MCP resources, or `GET /skill/` plus that path "
    "over HTTP."
)

COMMUNITY_TELEMETRY_URL = "https://mcp.blockscout.com"
COMMUNITY_TELEMETRY_ENDPOINT = "/v1/report_tool_usage"

# Sentinel event name for MCP resource reads. UPPERCASE so it can never collide
# with a tool function name (all tool names are snake_case/lowercase).
RESOURCE_READ_EVENT = "RESOURCE_READ"

ALLOW_LARGE_RESPONSE_HEADER = "X-Blockscout-Allow-Large-Response"

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

# Versioned domain-separation prefix for the PRO API key fingerprint hash. The "v1" is
# deliberate: it lets the hashing scheme be versioned later without silently colliding
# with old fingerprints. It is not a secret and provides domain separation, not
# brute-force resistance (PRO API keys are high-entropy, so preimage attacks are
# infeasible; a server-side HMAC pepper is deferred to a follow-up change).
PRO_API_KEY_HASH_PREFIX = "bs-pro-key-v1:"

# The three real authorization origins a key can come from, as computed by the
# ctx-derived helpers. Defined as a single Literal alias (not separate string
# constants) because a Literal[...] annotation cannot be built from string-constant
# variables; the model field and the helper return type both import this alias.
AuthOrigin = Literal["client", "server", "none"]

# Legacy sentinel used only at the Mixpanel layer as the default for community
# reports that predate the `auth_origin` field. Deliberately not part of `AuthOrigin`:
# it is never a valid report value and never returned by the helpers.
AUTH_ORIGIN_UNKNOWN = "unknown"

# A SHA-256 hex digest is always exactly 64 characters. This is the defensive
# max_length cap on the inbound community report's `api_key_fingerprint` field
# (mirroring the rationale documented for `_MAX_KEY_LENGTH` in pro_api_key_context.py);
# the field's `pattern` enforces the full exact shape.
PRO_API_KEY_FINGERPRINT_MAX_LENGTH = 64
