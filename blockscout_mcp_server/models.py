"""Pydantic models for standardized tool responses."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

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
class RecommendedChain(BaseModel):
    """Represents a popular blockchain with its essential identifiers."""

    name: str = Field(description="The common name of the blockchain (e.g., 'Ethereum').")
    chain_id: int = Field(description="The unique numeric identifier for the chain.")


class InstructionsData(BaseModel):
    """A structured representation of the server's operational instructions."""

    version: str = Field(description="The version of the Blockscout MCP server.")
    general_rules: list[str] = Field(
        description="A list of general operational rules for interacting with this server."
    )
    recommended_chains: list[RecommendedChain] = Field(
        description="A list of popular chains with their names and IDs, useful for quick lookups."
    )


# --- Model for get_contract_abi Data Payload ---
class ContractAbiData(BaseModel):
    """A structured representation of a smart contract's ABI."""

    abi: list | None = Field(description="The Application Binary Interface (ABI) of the smart contract.")


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
