from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ToolResponse, TransactionLogItem
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.tools.transaction._shared import (
    _process_and_truncate_log_items,
    create_items_pagination,
    extract_log_cursor_params,
)


@log_tool_invocation
async def get_transaction_logs(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    transaction_hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[TransactionLogItem]]:
    """
    Get comprehensive transaction logs.
    Unlike standard eth_getLogs, this tool returns enriched logs, primarily focusing on decoded event parameters with their types and values (if event decoding is applicable).
    Essential for analyzing smart contract events, tracking token transfers, monitoring DeFi protocol interactions, debugging event emissions, and understanding complex multi-contract transaction flows.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = f"/api/v2/transactions/{transaction_hash}/logs"
    params = {}

    apply_cursor_to_params(cursor, params)

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch transaction logs for {transaction_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction logs..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    original_items, was_truncated = _process_and_truncate_log_items(response_data.get("items", []))

    log_items_dicts: list[dict] = []
    for item in original_items:
        address_value = (
            item.get("address", {}).get("hash") if isinstance(item.get("address"), dict) else item.get("address")
        )
        curated_item = {
            "address": address_value,
            "block_number": item.get("block_number"),
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
        "- `address`: The contract address that emitted the log (string)",
        "- `block_number`: Block where the event was emitted",
        "- `index`: Log position within the block",
        "- `topics`: Raw indexed event parameters (first topic is event signature hash)",
        "- `data`: Raw non-indexed event parameters (hex encoded). **May be truncated.**",
        "- `decoded`: If available, the decoded event with its name and parameters",
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
                "If the full log data is crucial for your analysis, you can retrieve the complete, "
                "untruncated logs for this transaction programmatically. For example, using curl:"
            ),
            f'`curl "{base_url}/api/v2/transactions/{transaction_hash}/logs"`',
            "You would then need to parse the JSON response and find the specific log by its index.",
        ]

    sliced_items, pagination = create_items_pagination(
        items=log_items_dicts,
        page_size=config.logs_page_size,
        tool_name="get_transaction_logs",
        next_call_base_params={"chain_id": chain_id, "transaction_hash": transaction_hash},
        cursor_extractor=extract_log_cursor_params,
    )

    log_items = [TransactionLogItem(**item) for item in sliced_items]

    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction logs.")

    return build_tool_response(
        data=log_items,
        data_description=data_description,
        notes=notes,
        pagination=pagination,
    )
