"""Pydantic models for standardized tool responses."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# --- Generic Type Variable ---
T = TypeVar("T")


# --- Models for Pagination ---
class NextCallInfo(BaseModel):
    """A structured representation of the tool call required to get the next page."""

    tool_name: str = Field(description="The name of the tool to call for the next page.")
    params: dict[str, Any] = Field(
        description="A complete dictionary of parameters for the next tool call, including the new cursor."
    )


class PaginationInfo(BaseModel):
    """Contains the structured information needed to retrieve the next page of results."""

    next_call: NextCallInfo


# --- Model for get_latest_block Data Payload ---
class LatestBlockData(BaseModel):
    """Represents the essential data for the latest block."""

    block_number: int = Field(description="The block number (height) in the blockchain")
    timestamp: str = Field(description="The timestamp when the block was mined (ISO format)")


# --- Models for __get_instructions__ Data Payload ---
class ChainInfo(BaseModel):
    """Represents a blockchain with its essential identifiers."""

    name: str = Field(description="The common name of the blockchain (e.g., 'Ethereum').")
    chain_id: int = Field(description="The unique numeric identifier for the chain.")


class InstructionsData(BaseModel):
    """A structured representation of the server's operational instructions."""

    version: str = Field(description="The version of the Blockscout MCP server.")
    general_rules: list[str] = Field(
        description="A list of general operational rules for interacting with this server."
    )
    recommended_chains: list[ChainInfo] = Field(
        description="A list of popular chains with their names and IDs, useful for quick lookups."
    )


# --- Model for get_contract_abi Data Payload ---
class ContractAbiData(BaseModel):
    """A structured representation of a smart contract's ABI."""

    abi: list | None = Field(description="The Application Binary Interface (ABI) of the smart contract.")


# --- Model for lookup_token_by_symbol Data Payload ---
class TokenSearchResult(BaseModel):
    """Represents a single token found by a search query."""

    address: str = Field(description="The contract address of the token.")
    name: str = Field(description="The full name of the token (e.g., 'USD Coin').")
    symbol: str = Field(description="The symbol of the token (e.g., 'USDC').")
    token_type: str = Field(description="The token standard (e.g., 'ERC-20').")
    total_supply: str = Field(description="The total supply of the token.")
    circulating_market_cap: str | None = Field(description="The circulating market cap, if available.")
    exchange_rate: str | None = Field(description="The current exchange rate, if available.")
    is_smart_contract_verified: bool = Field(description="Indicates if the token's contract is verified.")
    is_verified_via_admin_panel: bool = Field(description="Indicates if the token is verified by the Blockscout team.")


# --- Models for get_address_info Data Payload ---
class AddressInfoData(BaseModel):
    """A structured representation of the combined address information."""

    basic_info: dict[str, Any] = Field(description="Core on-chain data for the address from the Blockscout API.")
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional metadata, such as public tags, from the Metadata service.",
    )


# --- Model for get_address_by_ens_name Data Payload ---
class EnsAddressData(BaseModel):
    """A structured representation of an ENS name resolution."""

    resolved_address: str | None = Field(
        None,
        description=("The resolved Ethereum address corresponding to the ENS name, or null if not found."),
    )


# --- Model for transaction_summary Data Payload ---
class TransactionSummaryData(BaseModel):
    """A structured representation of a transaction summary."""

    summary: str | None = Field(
        None,
        description="The human-readable summary of the transaction, or null if no summary is available.",
    )


# --- Models for get_transaction_info Data Payload ---
class TokenTransfer(BaseModel):
    """Represents a single token transfer within a transaction."""

    model_config = ConfigDict(extra="allow")

    from_address: str | None = Field(alias="from")
    to_address: str | None = Field(alias="to")
    token: dict[str, Any]
    transfer_type: str = Field(alias="type")


class DecodedInput(BaseModel):
    """Represents the decoded input data of a transaction."""

    model_config = ConfigDict(extra="allow")

    method_call: str
    method_id: str
    parameters: list[Any]


class TransactionInfoData(BaseModel):
    """Structured representation of get_transaction_info data."""

    model_config = ConfigDict(extra="allow")

    from_address: str | None = Field(default=None, alias="from")
    to_address: str | None = Field(default=None, alias="to")

    token_transfers: list[TokenTransfer] = Field(default_factory=list)
    decoded_input: DecodedInput | None = None

    raw_input: str | None = None
    raw_input_truncated: bool | None = None


# --- The Main Standardized Response Model ---
class ToolResponse(BaseModel, Generic[T]):
    """A standardized, structured response for all MCP tools, generic over the data payload type."""

    data: T = Field(description="The main data payload of the tool's response.")

    data_description: list[str] | None = Field(
        None,
        description="A list of notes explaining the structure, fields, or conventions of the 'data' payload.",
    )

    notes: list[str] | None = Field(
        None,
        description=(
            "A list of important contextual notes, such as warnings about data truncation or data quality issues."
        ),
    )

    instructions: list[str] | None = Field(
        None,
        description="A list of suggested follow-up actions or instructions for the LLM to plan its next steps.",
    )

    pagination: PaginationInfo | None = Field(
        None,
        description="Pagination information, present only if the 'data' is a single page of a larger result set.",
    )


# --- Model for get_block_info Data Payload ---
class BlockInfoData(BaseModel):
    """A structured representation of a block's information."""

    model_config = ConfigDict(extra="allow")

    block_details: dict[str, Any] = Field(description="A dictionary containing the detailed properties of the block.")
    transaction_hashes: list[str] | None = Field(
        None, description="A list of transaction hashes included in the block."
    )
