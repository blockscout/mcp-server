"""Specialized handler for processing transaction logs responses."""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ToolResponse, TransactionLogItem
from blockscout_mcp_server.tools.common import (
    _process_and_truncate_log_items,
    build_tool_response,
    create_items_pagination,
    extract_log_cursor_params,
)
from blockscout_mcp_server.tools.direct_api.dispatcher import register_handler


@register_handler(r"^/api/v2/transactions/(?P<transaction_hash>0x[a-fA-F0-9]{64})/logs/?$")
async def handle_transaction_logs(
    *,
    match: re.Match[str],
    response_json: dict[str, Any],
    chain_id: str,
    base_url: str,
    ctx: Context,  # noqa: ARG001 - reserved for future use in handlers
    query_params: dict[str, Any] | None = None,  # noqa: ARG001 - not used by this endpoint but required by dispatcher
) -> ToolResponse[list[TransactionLogItem]]:
    """Process the raw JSON response for a transaction logs request."""
    transaction_hash = match.group("transaction_hash")
    original_items, was_truncated = _process_and_truncate_log_items(response_json.get("items", []))

    log_items_dicts: list[dict[str, Any]] = []
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
        tool_name="direct_api_call",
        next_call_base_params={
            "chain_id": chain_id,
            "endpoint_path": f"/api/v2/transactions/{transaction_hash}/logs",
        },
        cursor_extractor=extract_log_cursor_params,
    )

    log_items = [TransactionLogItem(**item) for item in sliced_items]

    return build_tool_response(
        data=log_items,
        data_description=data_description,
        notes=notes,
        pagination=pagination,
    )
