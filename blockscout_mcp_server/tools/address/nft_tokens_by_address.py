from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import (
    NftCollectionHolding,
    NftCollectionInfo,
    NftTokenInstance,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


def extract_nft_cursor_params(item: dict) -> dict:
    """Extract cursor parameters from an NFT collection item for pagination continuation.

    This function determines which fields from the last item should be used
    as cursor parameters for the next page request. The returned dictionary
    is encoded and used in the `cursor` parameter for pagination.
    """
    token_info = item.get("token", {})
    return {
        "token_contract_address_hash": token_info.get("address_hash"),
        "token_type": token_info.get("type"),
        "items_count": 50,
    }


@log_tool_invocation
async def nft_tokens_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="NFT owner address")],
    ctx: Context,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[NftCollectionHolding]]:
    """
    Retrieve NFT tokens (ERC-721, ERC-404, ERC-1155) owned by an address, grouped by collection.
    Provides collection details (type, address, name, symbol, total supply, holder count) and individual token instance data (ID, name, description, external URL, metadata attributes).
    Essential for a detailed overview of an address's digital collectibles and their associated collection data.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501

    api_path = f"/api/v2/addresses/{address}/nft/collections"
    params = {"type": "ERC-721,ERC-404,ERC-1155"}

    apply_cursor_to_params(cursor, params)

    await report_and_log_progress(
        ctx, progress=0.0, total=2.0, message=f"Starting to fetch NFT tokens for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching NFT data..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched NFT data.")

    # Process all items first to prepare for pagination
    original_items = response_data.get("items", [])
    processed_items = []

    for item in original_items:
        token = item.get("token", {})

        token_instances = []
        for instance in item.get("token_instances", []):
            # To preserve the LLM context, only specific fields for NFT instances are
            # added to the response
            metadata = instance.get("metadata", {}) or {}
            token_instances.append(
                {
                    "id": instance.get("id", ""),
                    "name": metadata.get("name"),
                    "description": metadata.get("description"),
                    "image_url": metadata.get("image_url"),
                    "external_app_url": metadata.get("external_url"),
                    "metadata_attributes": metadata.get("attributes"),
                }
            )

        # To preserve the LLM context, only specific fields for NFT collections are
        # added to the response
        collection_info = {
            "type": token.get("type", ""),
            "address": token.get("address_hash", ""),
            "name": token.get("name"),
            "symbol": token.get("symbol"),
            "holders_count": token.get("holders_count") or 0,
            "total_supply": token.get("total_supply") or 0,
        }

        processed_item = {
            "token": token,  # Keep original token info for cursor extraction
            "amount": item.get("amount", ""),
            "token_instances": token_instances,
            "collection_info": collection_info,
        }
        processed_items.append(processed_item)

    # Use create_items_pagination helper to handle slicing and pagination
    sliced_items, pagination = create_items_pagination(
        items=processed_items,
        page_size=config.nft_page_size,
        tool_name="nft_tokens_by_address",
        next_call_base_params={
            "chain_id": chain_id,
            "address": address,
        },
        cursor_extractor=extract_nft_cursor_params,
        force_pagination=False,
    )

    # Convert sliced items to NftCollectionHolding objects
    nft_holdings: list[NftCollectionHolding] = []
    for item in sliced_items:
        collection_info = NftCollectionInfo(**item["collection_info"])
        token_instances = [NftTokenInstance(**instance) for instance in item["token_instances"]]
        nft_holdings.append(
            NftCollectionHolding(
                collection=collection_info,
                amount=item["amount"],
                token_instances=token_instances,
            )
        )

    return build_tool_response(data=nft_holdings, pagination=pagination)
