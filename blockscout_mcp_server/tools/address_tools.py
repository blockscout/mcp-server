import asyncio
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import (
    AddressInfoData,
    AddressLogItem,
    NextCallInfo,
    NftCollectionHolding,
    NftCollectionInfo,
    NftTokenInstance,
    PaginationInfo,
    TokenHoldingData,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import (
    _process_and_truncate_log_items,
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    encode_cursor,
    extract_log_cursor_params,
    get_blockscout_base_url,
    make_blockscout_request,
    make_metadata_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def get_address_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address to get information about")],
    ctx: Context,
) -> ToolResponse[AddressInfoData]:
    """
    Get comprehensive information about an address, including:
    - Address existence check
    - Native token (ETH) balance (provided as is, without adjusting by decimals)
    - ENS name association (if any)
    - Contract status (whether the address is a contract, whether it is verified)
    - Proxy contract information (if applicable): determines if a smart contract is a proxy contract (which forwards calls to implementation contracts), including proxy type and implementation addresses
    - Token details (if the contract is a token): name, symbol, decimals, total supply, etc.
    Essential for address analysis, contract investigation, token research, and DeFi protocol analysis.
    """  # noqa: E501
    await report_and_log_progress(
        ctx, progress=0.0, total=3.0, message=f"Starting to fetch address info for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)
    await report_and_log_progress(
        ctx, progress=1.0, total=3.0, message="Resolved Blockscout instance URL. Fetching data..."
    )

    blockscout_api_path = f"/api/v2/addresses/{address}"
    metadata_api_path = "/api/v1/metadata"
    metadata_params = {"addresses": address, "chainId": chain_id}

    address_info_result, metadata_result = await asyncio.gather(
        make_blockscout_request(base_url=base_url, api_path=blockscout_api_path),
        make_metadata_request(api_path=metadata_api_path, params=metadata_params),
        return_exceptions=True,
    )

    if isinstance(address_info_result, Exception):
        raise address_info_result

    await report_and_log_progress(ctx, progress=2.0, total=3.0, message="Fetched basic address info.")

    notes = None
    if isinstance(metadata_result, Exception):
        notes = [f"Could not retrieve address metadata. The 'metadata' field is null. Error: {metadata_result}"]
        metadata_data = None
    elif metadata_result.get("addresses"):
        address_key = next(
            (key for key in metadata_result["addresses"] if key.lower() == address.lower()),
            None,
        )
        metadata_data = metadata_result["addresses"].get(address_key) if address_key else None
    else:
        metadata_data = None

    address_data = AddressInfoData(basic_info=address_info_result, metadata=metadata_data)

    await report_and_log_progress(ctx, progress=3.0, total=3.0, message="Successfully fetched all address data.")

    return build_tool_response(data=address_data, notes=notes)


@log_tool_invocation
async def get_tokens_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Wallet address")],
    ctx: Context,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[TokenHoldingData]]:
    """
    Get comprehensive ERC20 token holdings for an address with enriched metadata and market data.
    Returns detailed token information including contract details (name, symbol, decimals), market metrics (exchange rate, market cap, volume), holders count, and actual balance (provided as is, without adjusting by decimals).
    Essential for portfolio analysis, wallet auditing, and DeFi position tracking.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = f"/api/v2/addresses/{address}/tokens"
    params = {"tokens": "ERC-20"}

    # Add pagination parameters if provided via cursor
    apply_cursor_to_params(cursor, params)

    # Report start of operation
    await report_and_log_progress(
        ctx, progress=0.0, total=2.0, message=f"Starting to fetch token holdings for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching token data..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched token data.")

    items_data = response_data.get("items", [])
    token_holdings = []
    for item in items_data:
        # To preserve the LLM context, only specific fields are added to the response
        token = item.get("token", {})
        token_holdings.append(
            TokenHoldingData(
                address=token.get("address_hash", ""),
                name=token.get("name") or "",
                symbol=token.get("symbol") or "",
                decimals=token.get("decimals") or "",
                total_supply=token.get("total_supply") or "",
                circulating_market_cap=token.get("circulating_market_cap"),
                exchange_rate=token.get("exchange_rate"),
                holders_count=token.get("holders_count") or "",
                balance=item.get("value", ""),
            )
        )

    # Since there could be more than one page of tokens for the same address,
    # the pagination information is extracted from API response and added explicitly
    # to the tool response
    pagination = None
    next_page_params = response_data.get("next_page_params")
    if next_page_params:
        next_cursor = encode_cursor(next_page_params)
        pagination = PaginationInfo(
            next_call=NextCallInfo(
                tool_name="get_tokens_by_address",
                params={
                    "chain_id": chain_id,
                    "address": address,
                    "cursor": next_cursor,
                },
            )
        )

    return build_tool_response(data=token_holdings, pagination=pagination)


def extract_nft_cursor_params(item: dict) -> dict:
    """Extract cursor parameters from an NFT collection item for pagination continuation.

    This function determines which fields from the last item should be used
    as cursor parameters for the next page request. The returned dictionary
    will be encoded as an opaque cursor string.
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


# Note: This tool has been deprecated from the MCP interface as of v0.6.0.
# It was found to be frequently misused by LLMs, which preferred it over the
# more efficient workflow of using `get_transactions_by_address` (with time filters)
# followed by `get_transaction_logs`.
# The implementation is preserved here for potential future use if a specific,
# valid use case is identified. The REST endpoint /v1/get_address_logs now
# returns a static deprecation notice.


@log_tool_invocation
async def get_address_logs(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Account address")],
    ctx: Context,
    cursor: Annotated[
        str | None,
        Field(
            description="The pagination cursor from a previous response to get the next page of results.",
        ),
    ] = None,
) -> ToolResponse[list[AddressLogItem]]:
    """
    Get comprehensive logs emitted by a specific address.
    Returns enriched logs, primarily focusing on decoded event parameters with their types and values (if event decoding is applicable).
    Essential for analyzing smart contract events emitted by specific addresses, monitoring token contract activities, tracking DeFi protocol state changes, debugging contract event emissions, and understanding address-specific event history flows.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = f"/api/v2/addresses/{address}/logs"
    params = {}

    # Add pagination parameters if provided via cursor
    apply_cursor_to_params(cursor, params)

    # Report start of operation
    await report_and_log_progress(
        ctx, progress=0.0, total=2.0, message=f"Starting to fetch address logs for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching address logs..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched address logs.")

    original_items, was_truncated = _process_and_truncate_log_items(response_data.get("items", []))

    log_items_dicts: list[dict] = []
    # To preserve the LLM context, only specific fields are added to the response
    for item in original_items:
        curated_item = {
            "block_number": item.get("block_number"),
            "transaction_hash": item.get("transaction_hash"),
            "topics": item.get("topics"),
            "data": item.get("data"),
            "decoded": item.get("decoded"),
            "index": item.get("index"),
        }
        if item.get("data_truncated"):
            curated_item["data_truncated"] = True

        log_items_dicts.append(curated_item)

    data_description = [
        "Items Structure:",
        "- `block_number`: Block where the event was emitted",
        "- `transaction_hash`: Transaction that triggered the event",
        "- `index`: Log position within the block",
        "- `topics`: Raw indexed event parameters (first topic is event signature hash)",
        "- `data`: Raw non-indexed event parameters (hex encoded). **May be truncated.**",
        "- `data_truncated`: (Optional) `true` if the `data` or `decoded` field was shortened.",
        "Event Decoding in `decoded` field:",
        (
            "- `method_call`: **Actually the event signature** "
            '(e.g., "Transfer(address indexed from, address indexed to, uint256 value)")'
        ),
        "- `method_id`: **Actually the event signature hash** (first 4 bytes of keccak256 hash)",
        "- `parameters`: Decoded event parameters with names, types, values, and indexing status",
    ]

    notes = None
    if was_truncated:
        notes = [
            (
                "One or more log items in this response had a `data` field that was "
                'too large and has been truncated (indicated by `"data_truncated": true`).'
            ),
            (
                "If the full log data is crucial for your analysis, you must first get "
                "the `transaction_hash` from the specific log item. Then, you can retrieve "
                "all logs for that single transaction programmatically. For example, using curl:"
            ),
            f'`curl "{base_url}/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs"`',
        ]

    sliced_items, pagination = create_items_pagination(
        items=log_items_dicts,
        page_size=config.logs_page_size,
        tool_name="get_address_logs",
        next_call_base_params={"chain_id": chain_id, "address": address},
        cursor_extractor=extract_log_cursor_params,
    )

    sliced_log_items = [AddressLogItem(**item) for item in sliced_items]

    return build_tool_response(
        data=sliced_log_items,
        data_description=data_description,
        notes=notes,
        pagination=pagination,
    )
