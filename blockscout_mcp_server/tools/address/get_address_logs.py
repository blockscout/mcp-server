from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AddressLogItem, ToolResponse
from blockscout_mcp_server.tools.common import (
    _process_and_truncate_log_items,
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    extract_log_cursor_params,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


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
