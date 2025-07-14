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

    next_call: NextCallInfo = Field(description="The structured tool call required to fetch the subsequent page.")


# --- Model for get_latest_block Data Payload ---
class LatestBlockData(BaseModel):
    """Represents the essential data for the latest block."""

    block_number: int = Field(description="The block number (height) in the blockchain")
    timestamp: str = Field(description="The timestamp when the block was mined (ISO format)")


# --- Model for __get_instructions__ Data Payload ---
class ChainInfo(BaseModel):
    """Represents a blockchain with its essential identifiers."""

    name: str = Field(description="The common name of the blockchain (e.g., 'Ethereum').")
    chain_id: str = Field(description="The unique identifier for the chain.")


# --- Model for __get_instructions__ Data Payload ---
class ChainIdGuidance(BaseModel):
    """A structured representation of chain ID guidance combining rules and recommendations."""

    rules: str = Field(description="Rules for chain ID selection and usage.")
    recommended_chains: list[ChainInfo] = Field(
        description="A list of popular chains with their names and IDs, useful for quick lookups."
    )


class InstructionsData(BaseModel):
    """A structured representation of the server's operational instructions."""

    version: str = Field(description="The version of the Blockscout MCP server.")
    error_handling_rules: str = Field(description="Rules for handling network errors and retries.")
    chain_id_guidance: ChainIdGuidance = Field(description="Comprehensive guidance for chain ID selection and usage.")
    pagination_rules: str = Field(description="Rules for handling paginated responses and data retrieval.")
    time_based_query_rules: str = Field(description="Rules for executing time-based blockchain queries efficiently.")
    block_time_estimation_rules: str = Field(description="Rules for mathematical block time estimation and navigation.")
    efficiency_optimization_rules: str = Field(description="Rules for optimizing query strategies and performance.")


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


# --- Model for get_address_info Data Payload ---
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

    summary: list[dict] | None = Field(
        None,
        description=(
            "List of summary objects for generating human-readable transaction descriptions, "
            "or null if no summary data is available."
        ),
    )


# --- Model for get_transaction_info Data Payload ---
class TokenTransfer(BaseModel):
    """Represents a single token transfer within a transaction."""

    model_config = ConfigDict(extra="allow")  # External APIs may add new fields; allow them to avoid validation errors

    from_address: str | None = Field(alias="from", description="Sender address of the token transfer if available.")
    to_address: str | None = Field(alias="to", description="Recipient address of the token transfer if available.")
    token: dict[str, Any] = Field(description="Token metadata dictionary associated with the transfer.")
    transfer_type: str = Field(alias="type", description="Type of transfer (e.g., 'transfer', 'mint').")


# --- Model for get_transaction_info Data Payload ---
class DecodedInput(BaseModel):
    """Represents the decoded input data of a transaction."""

    model_config = ConfigDict(extra="allow")  # External APIs may add new fields; allow them to avoid validation errors

    method_call: str = Field(description="Name of the called method.")
    method_id: str = Field(description="Identifier of the called method.")
    parameters: list[Any] = Field(description="List of decoded input parameters for the method call.")


# --- Model for get_transaction_info Data Payload ---
class TransactionInfoData(BaseModel):
    """Structured representation of get_transaction_info data."""

    model_config = ConfigDict(extra="allow")  # External APIs may add new fields; allow them to avoid validation errors

    from_address: str | None = Field(
        default=None,
        alias="from",
        description="Sender of the transaction if available.",
    )
    to_address: str | None = Field(
        default=None,
        alias="to",
        description="Recipient of the transaction if available.",
    )

    token_transfers: list[TokenTransfer] = Field(
        default_factory=list, description="List of token transfers related to the transaction."
    )
    decoded_input: DecodedInput | None = Field(
        default=None,
        description="Decoded method input if available.",
    )

    raw_input: str | None = Field(default=None, description="Raw transaction input data if returned.")
    raw_input_truncated: bool | None = Field(default=None, description="Indicates if raw_input was truncated.")


# --- Model for get_transactions_by_address and get_token_transfers_by_address Data Payload ---
class AdvancedFilterItem(BaseModel):
    """Represents a single item from the advanced filter API response."""

    model_config = ConfigDict(extra="allow")  # External APIs may add new fields; allow them to avoid validation errors

    from_address: str | None = Field(
        default=None,
        alias="from",
        description="The sender address.",
    )
    to_address: str | None = Field(
        default=None,
        alias="to",
        description="The recipient address.",
    )


# --- Model for get_tokens_by_address Data Payload ---
class TokenHoldingData(BaseModel):
    """Represents a single token holding with its associated metadata."""

    address: str = Field(description="The contract address of the token.")
    name: str = Field(description="The full name of the token (e.g., 'USD Coin').")
    symbol: str = Field(description="The symbol of the token (e.g., 'USDC').")
    decimals: str = Field(description="The number of decimals the token uses.")
    total_supply: str = Field(description="The total supply of the token.")
    circulating_market_cap: str | None = Field(description="The circulating market cap, if available.")
    exchange_rate: str | None = Field(description="The current exchange rate, if available.")
    holders_count: str = Field(description="The number of addresses holding this token.")
    balance: str = Field(description="The token balance for the queried address (unadjusted for decimals).")


# --- Model for nft_tokens_by_address Data Payload ---
class NftTokenInstance(BaseModel):
    """Represents a single NFT instance with its metadata."""

    id: str = Field(description="The unique identifier of the NFT token instance.")
    name: str | None = Field(None, description="The name of the NFT, extracted from its metadata.")
    description: str | None = Field(None, description="The description of the NFT, extracted from its metadata.")
    image_url: str | None = Field(None, description="A URL for the NFT's image, from its metadata.")
    external_app_url: str | None = Field(
        None,
        description="A URL to an external site or application related to the NFT.",  # noqa: E501
    )
    metadata_attributes: list | dict | None = Field(
        None,
        description="The metadata attributes (traits) associated with the NFT.",
    )


# --- Model for nft_tokens_by_address Data Payload ---
class NftCollectionInfo(BaseModel):
    """Represents the metadata for an NFT collection."""

    type: str = Field(description="The token standard of the collection.")
    address: str = Field(description="The smart contract address of the NFT collection.")
    name: str | None = Field(None, description="The name of the collection.")
    symbol: str | None = Field(None, description="The symbol of the collection.")
    holders_count: int = Field(description="The number of unique addresses that hold a token from this collection.")
    total_supply: int = Field(description="The total number of tokens in the collection.")


# --- Model for nft_tokens_by_address Data Payload ---
class NftCollectionHolding(BaseModel):
    """Represents an address's holding in a single NFT collection."""

    collection: NftCollectionInfo = Field(description="The details of the NFT collection.")
    amount: str = Field(description="The number of tokens from this collection owned by the address.")
    token_instances: list[NftTokenInstance] = Field(
        description="A list of the specific NFT instances owned by the address."
    )


# --- Model for get_address_logs and get_transaction_logs Data Payloads ---
class LogItemBase(BaseModel):
    """Common fields for log items from Blockscout."""

    model_config = ConfigDict(extra="allow")  # Just to allow `data_truncated` field to be added to the response

    block_number: int | None = Field(None, description="The block where the event was emitted.")
    topics: list[str | None] | None = Field(None, description="Raw indexed event parameters.")
    data: str | None = Field(
        None,
        description="Raw non-indexed event parameters. May be truncated.",
    )
    decoded: dict[str, Any] | None = Field(None, description="Decoded event parameters, if available.")
    index: int | None = Field(None, description="The log's position within the block.")


# --- Model for get_address_logs Data Payload ---
class AddressLogItem(LogItemBase):
    """Represents a single log item when the address is redundant."""

    transaction_hash: str | None = Field(None, description="The transaction that triggered the event.")


# --- Model for get_transaction_logs Data Payload ---
class TransactionLogItem(LogItemBase):
    """Represents a single log item with its originating contract address."""

    address: str | None = Field(
        None,
        description="The contract address that emitted the log.",
    )


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

    model_config = ConfigDict(extra="allow")  # External APIs may add new fields; allow them to avoid validation errors

    block_details: dict[str, Any] = Field(description="A dictionary containing the detailed properties of the block.")
    transaction_hashes: list[str] | None = Field(
        None, description="A list of transaction hashes included in the block."
    )
