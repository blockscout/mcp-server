import asyncio
import json
from typing import Annotated, Dict, Optional
from pydantic import Field
from blockscout_mcp_server.tools.common import (
    make_blockscout_request,
    get_blockscout_base_url,
    encode_cursor,
    decode_cursor,
    InvalidCursorError,
    make_metadata_request,
    report_and_log_progress,
)
from mcp.server.fastmcp import Context

async def get_address_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address to get information about")],
    ctx: Context
) -> str:
    """
    Get comprehensive information about an address, including:
    - Address existence check
    - Native token (ETH) balance (provided as is, without adjusting by decimals)
    - ENS name association (if any)
    - Contract status (whether the address is a contract, whether it is verified)
    - Proxy contract information (if applicable): determines if a smart contract is a proxy contract (which forwards calls to implementation contracts), including proxy type and implementation addresses
    - Token details (if the contract is a token): name, symbol, decimals, total supply, etc.
    Essential for address analysis, contract investigation, token research, and DeFi protocol analysis.
    """
    await report_and_log_progress(
        ctx, progress=0.0, total=3.0,
        message=f"Starting to fetch address info for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)
    await report_and_log_progress(
        ctx, progress=1.0, total=3.0,
        message="Resolved Blockscout instance URL. Fetching data..."
    )

    blockscout_api_path = f"/api/v2/addresses/{address}"
    metadata_api_path = "/api/v1/metadata"
    metadata_params = {"addresses": address, "chainId": chain_id}

    address_info_result, metadata_result = await asyncio.gather(
        make_blockscout_request(base_url=base_url, api_path=blockscout_api_path),
        make_metadata_request(api_path=metadata_api_path, params=metadata_params),
        return_exceptions=True
    )

    output_parts = []

    if isinstance(address_info_result, Exception):
        return f"Error fetching basic address info: {address_info_result}"

    output_parts.append("Basic address info:")
    output_parts.append(json.dumps(address_info_result))
    await report_and_log_progress(
        ctx, progress=2.0, total=3.0, message="Fetched basic address info."
    )

    if not isinstance(metadata_result, Exception) and metadata_result.get("addresses"):
        # Safely look up the metadata for the exact address requested,
        # ignoring case differences in the API response keys
        address_key = next(
            (key for key in metadata_result["addresses"] if key.lower() == address.lower()),
            None,
        )
        if address_key:
            address_metadata = metadata_result["addresses"][address_key]
            if address_metadata:
                output_parts.append("\nMetadata associated with the address:")
                output_parts.append(json.dumps(address_metadata))

    await report_and_log_progress(
        ctx, progress=3.0, total=3.0,
        message="Successfully fetched all address data."
    )

    return "\n".join(output_parts)

async def get_tokens_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Wallet address")],
    ctx: Context,
    cursor: Annotated[
        Optional[str],
        Field(
            description="The pagination cursor from a previous response to get the next page of results."
        ),
    ] = None,
) -> str:
    """
    Get comprehensive ERC20 token holdings for an address with enriched metadata and market data.
    Returns detailed token information including contract details (name, symbol, decimals), market metrics (exchange rate, market cap, volume), holders count, and actual balance (provided as is, without adjusting by decimals).
    Supports pagination.
    Essential for portfolio analysis, wallet auditing, and DeFi position tracking.
    """
    api_path = f"/api/v2/addresses/{address}/tokens"
    params = {"tokens": "ERC-20"}
    
    # Add pagination parameters if provided via cursor
    if cursor:
        try:
            decoded_params = decode_cursor(cursor)
            params.update(decoded_params)
        except InvalidCursorError:
            return (
                "Error: Invalid or expired pagination cursor. Please make a new request without the cursor to start over."
            )
    
    # Report start of operation
    await report_and_log_progress(
        ctx, progress=0.0, total=2.0,
        message=f"Starting to fetch token holdings for {address} on chain {chain_id}..."
    )
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0,
        message="Resolved Blockscout instance URL. Fetching token data..."
    )
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)
    
    # Report completion
    await report_and_log_progress(
        ctx, progress=2.0, total=2.0, message="Successfully fetched token data."
    )
    
    # Process the response data and format it according to the responseTemplate
    items_data = response_data.get("items", [])
    output_parts = ["["]  # Start of JSON array
    
    for i, item in enumerate(items_data):
        token = item.get("token", {})
        # Format each item as a JSON-like string block
        item_str = f"""
  {{
    "address": "{token.get("address_hash", "")}",
    "name": "{token.get("name", "")}",
    "symbol": "{token.get("symbol", "")}",
    "decimals": "{token.get("decimals", "")}",
    "total_supply": "{token.get("total_supply", "")}",
    "circulating_market_cap": "{token.get("circulating_market_cap", "")}",
    "exchange_rate": "{token.get("exchange_rate", "")}",
    "volume_24h": "{token.get("volume_24h", "")}",
    "holders_count": "{token.get("holders_count", "")}",
    "balance": "{item.get("value", "")}"
  }}"""
        output_parts.append(item_str)
        if i < len(items_data) - 1:
            output_parts.append(",")
    
    output_parts.append("]")  # End of JSON array
    
    # Add pagination hint if next_page_params exists
    next_page_params = response_data.get("next_page_params")
    if next_page_params:
        next_cursor = encode_cursor(next_page_params)
        pagination_hint = f"""

----
To get the next page call get_tokens_by_address(chain_id="{chain_id}", address="{address}", cursor="{next_cursor}")"""
        output_parts.append(pagination_hint)
    
    return "".join(output_parts) 

async def nft_tokens_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="NFT owner address")],
    ctx: Context,
    cursor: Annotated[
        Optional[str],
        Field(
            description="The pagination cursor from a previous response to get the next page of results."
        ),
    ] = None,
) -> str:
    """
    Retrieve NFT tokens (ERC-721, ERC-404, ERC-1155) owned by an address, grouped by collection.
    Provides collection details (type, address, name, symbol, total supply, holder count) and individual token instance data (ID, name, description, external URL, metadata attributes).
    Essential for a detailed overview of an address's digital collectibles and their associated collection data.
    """
    api_path = f"/api/v2/addresses/{address}/nft/collections"
    params = {"type": "ERC-721,ERC-404,ERC-1155"}

    # Add pagination parameters if provided via cursor
    if cursor:
        try:
            decoded_params = decode_cursor(cursor)
            params.update(decoded_params)
        except InvalidCursorError:
            return (
                "Error: Invalid or expired pagination cursor. Please make a new request without the cursor to start over."
            )
    
    # Report start of operation
    await report_and_log_progress(
        ctx, progress=0.0, total=2.0,
        message=f"Starting to fetch NFT tokens for {address} on chain {chain_id}..."
    )
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0,
        message="Resolved Blockscout instance URL. Fetching NFT data..."
    )
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)
    
    # Report completion
    await report_and_log_progress(
        ctx, progress=2.0, total=2.0, message="Successfully fetched NFT data."
    )
    
    # Process the response data and format it
    items_data = response_data.get("items", [])
    output_parts = ["["]  # Start of JSON array

    for i, item in enumerate(items_data):
        token = item.get("token", {})

        # Format token instances
        token_instances = []
        for instance in item.get("token_instances", []):
            instance_data = {
                "id": instance.get("id", "")
            }

            # Add metadata if available
            metadata = instance.get("metadata", {})
            if metadata:
                if metadata.get("name"):
                    instance_data["name"] = metadata.get("name")
                if metadata.get("description"):
                    instance_data["description"] = metadata.get("description")
                if metadata.get("external_url"):
                    instance_data["external_app_url"] = metadata.get("external_url")
                if metadata.get("attributes"):
                    instance_data["metadata_attributes"] = metadata.get("attributes")

            token_instances.append(instance_data)

        # Format collection with its tokens
        collection_data = {
            "collection": {
                "type": token.get("type", ""),
                "address": token.get("address_hash", ""),
                "name": token.get("name", ""),
                "symbol": token.get("symbol", ""),
                "holders_count": token.get("holders_count", 0),
                "total_supply": token.get("total_supply", 0)
            },
            "amount": item.get("amount", ""),
            "token_instances": token_instances
        }

        item_str = json.dumps(collection_data)
        output_parts.append(item_str)
        if i < len(items_data) - 1:
            output_parts.append(",")

    output_parts.append("]")  # End of JSON array

    # Add pagination hint if next_page_params exists
    next_page_params = response_data.get("next_page_params")
    if next_page_params:
        next_cursor = encode_cursor(next_page_params)
        pagination_hint = f"""

----
To get the next page call nft_tokens_by_address(chain_id=\"{chain_id}\", address=\"{address}\", cursor=\"{next_cursor}\")"""
        output_parts.append(pagination_hint)

    return "".join(output_parts)

async def get_address_logs(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Account address")],
    ctx: Context,
    cursor: Annotated[
        Optional[str],
        Field(
            description="The pagination cursor from a previous response to get the next page of results."
        ),
    ] = None,
) -> str:
    """
    Get comprehensive logs emitted by a specific address.
    Returns enriched logs, primarily focusing on decoded event parameters with their types and values (if event decoding is applicable).
    Essential for analyzing smart contract events emitted by specific addresses, monitoring token contract activities, tracking DeFi protocol state changes, debugging contract event emissions, and understanding address-specific event history flows.
    """
    api_path = f"/api/v2/addresses/{address}/logs"
    params = {}
    
    # Add pagination parameters if provided via cursor
    if cursor:
        try:
            decoded_params = decode_cursor(cursor)
            params.update(decoded_params)
        except InvalidCursorError:
            return (
                "Error: Invalid or expired pagination cursor. Please make a new request without the cursor to start over."
            )
    
    # Report start of operation
    await report_and_log_progress(
        ctx, progress=0.0, total=2.0,
        message=f"Starting to fetch address logs for {address} on chain {chain_id}..."
    )
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0,
        message="Resolved Blockscout instance URL. Fetching address logs..."
    )
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    # Report completion
    await report_and_log_progress(
        ctx, progress=2.0, total=2.0,
        message="Successfully fetched address logs."
    )

    original_items = response_data.get("items", [])

    transformed_items = [
        {
            "block_number": item.get("block_number"),
            "data": item.get("data"),
            "decoded": item.get("decoded"),
            "index": item.get("index"),
            "topics": item.get("topics"),
            "transaction_hash": item.get("transaction_hash"),
        }
        for item in original_items
    ]

    # Create a dictionary containing ONLY the transformed items.
    transformed_response = {
        "items": transformed_items,
    }

    logs_json_str = json.dumps(transformed_response)  # Compact JSON
    
    prefix = """**Items Structure:**
    - `block_number`: Block where the event was emitted
    - `transaction_hash`: Transaction that triggered the event
    - `index`: Log position within the block
    - `topics`: Raw indexed event parameters (first topic is event signature hash)
    - `data`: Raw non-indexed event parameters (hex encoded)

**Event Decoding in `decoded` field:**
- `method_call`: **Actually the event signature** (e.g., "Transfer(address indexed from, address indexed to, uint256 value)")
- `method_id`: **Actually the event signature hash** (first 4 bytes of keccak256 hash)
- `parameters`: Decoded event parameters with names, types, values, and indexing status

**Address logs JSON:**
"""
    
    output = f"{prefix}{logs_json_str}"
    # Add pagination hint if next_page_params exists
    next_page_params = response_data.get("next_page_params")
    if next_page_params:
        next_cursor = encode_cursor(next_page_params)
        pagination_hint = f"""

----
To get the next page call get_address_logs(chain_id="{chain_id}", address="{address}", cursor="{next_cursor}")"""
        output += pagination_hint
    return output 