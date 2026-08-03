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

# ---------------------------------------------------------------------------
# Session-gated free tier (issue #442) — agent-facing string contracts.
#
# These five constants are load-bearing: they are asserted verbatim by tests
# and carry what the deleted "MANDATORY" sentence used to. Do not paraphrase
# or substring-match them away; see the Issue #442 implementation plan
# (Phase 3) for the wording rationale behind each one.
# ---------------------------------------------------------------------------

# Used for both a missing `session_id` and a MAC-invalid one. The dual-surface
# phrasing follows the `SKILL_POINTER_TEXT_TEMPLATE` precedent above: MCP
# registers only `__unlock_blockchain_analysis__` (dunders included) while REST
# serves `/v1/unlock_blockchain_analysis`, so a bare `unlock_blockchain_analysis`
# would name a tool that does not exist on either surface.
SESSION_ID_REQUIRED_MESSAGE = (
    "A valid `session_id` is required. If you have not yet called "
    "`__unlock_blockchain_analysis__` (MCP) / `GET /v1/unlock_blockchain_analysis` (REST) "
    "in this session, call it now and pass the returned `session_id` with this call. If you "
    "already called it, the session id is in your context — find it and reuse it; do not call "
    "it again."
)

# Used for both a valid-but-expired token and an exhausted budget — the two
# must be indistinguishable to the agent. "initialize the session" is
# deliberately transport-neutral so the shared string misnames no surface.
SESSION_OVER_MESSAGE = (
    "This session's `session_id` can no longer be used to access Blockscout data. Relay to the "
    "user: to continue, obtain a Blockscout PRO API key at https://mcp.blockscout.com and add it "
    "to the MCP client configuration; it takes effect in a new session after the client is "
    "reconfigured. Do not retry this call and do not initialize the session again."
)

# Runtime store fault. Deliberately non-terminal: it must read as temporary
# and server-side, and must contain none of the terminal markers above
# ("do not retry" / "do not initialize"), because those are what suppress
# retries.
SESSION_STORE_UNAVAILABLE_MESSAGE = (
    "Unauthenticated access is temporarily unavailable. Requests with a client-supplied PRO API "
    "key are unaffected — relay to the user: obtain a key at https://mcp.blockscout.com. "
    "Otherwise, retry later."
)

# The remaining-budget note (Phase 5). `{remaining}` and `{max_calls}` are
# filled in per response.
SESSION_BUDGET_NOTE_TEMPLATE = (
    "Free session budget: {remaining} of {max_calls} tool calls remaining. Requests authorized "
    "with a client-supplied Blockscout PRO API key are not metered — get a key at "
    "https://mcp.blockscout.com."
)

# The entire parameter description shared by all 15 gated tools (Phase 7).
# Deliberately minimal: it names no source and no condition, so it creates no
# pull toward an unlock call for PRO-key-exempt agents or ungated deployments.
SESSION_ID_PARAM_DESCRIPTION = "Opaque session identifier."
