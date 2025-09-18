from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    get_blockscout_base_url,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.tools.transaction._shared import (
    _fetch_filtered_transactions_with_smart_pagination,
    _transform_advanced_filter_item,
    create_items_pagination,
    extract_advanced_filters_cursor_params,
)


@log_tool_invocation
async def get_transactions_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either sender or receiver of the transaction")],
    ctx: Context,
    age_from: Annotated[str | None, Field(description="Start date and time (e.g 2025-05-22T23:00:00.00Z).")] = None,
    age_to: Annotated[str | None, Field(description="End date and time (e.g 2025-05-22T22:30:00.00Z).")] = None,
    methods: Annotated[
        str | None,
        Field(description="A method signature to filter transactions by (e.g 0x304e6ade)"),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[AdvancedFilterItem]]:
    """
    Retrieves native currency transfers and smart contract interactions (calls, internal txs) for an address.
    **EXCLUDES TOKEN TRANSFERS**: Filters out direct token balance changes (ERC-20, etc.). You'll see calls *to* token contracts, but not the `Transfer` events. For token history, use `get_token_transfers_by_address`.
    A single tx can have multiple records from internal calls; use `internal_transaction_index` for execution order.
    Use cases:
      - `get_transactions_by_address(address, age_from)` - get all txs to/from the address since a given date.
      - `get_transactions_by_address(address, age_from, age_to)` - get all txs to/from the address between given dates.
      - `get_transactions_by_address(address, age_from, age_to, methods)` - get all txs to/from the address between given dates, filtered by method.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address,
    }
    if age_from:
        query_params["age_from"] = age_from
    if age_to:
        query_params["age_to"] = age_to
    if methods:
        query_params["methods"] = methods

    apply_cursor_to_params(cursor, query_params)

    tool_overall_total_steps = 12.0

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=tool_overall_total_steps,
        message=f"Starting to fetch transactions for {address} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=tool_overall_total_steps,
        message="Resolved Blockscout instance URL. Now fetching transactions...",
    )

    filtered_items, has_more_pages = await _fetch_filtered_transactions_with_smart_pagination(
        base_url=base_url,
        api_path=api_path,
        initial_params=query_params,
        target_page_size=config.advanced_filters_page_size,
        ctx=ctx,
        progress_start_step=2.0,
        total_steps=tool_overall_total_steps,
    )

    await report_and_log_progress(
        ctx,
        progress=tool_overall_total_steps,
        total=tool_overall_total_steps,
        message="Successfully fetched transaction data.",
    )

    fields_to_remove = [
        "total",
        "token",
        "token_transfer_batch_index",
        "token_transfer_index",
    ]

    final_items, pagination = create_items_pagination(
        items=filtered_items,
        page_size=config.advanced_filters_page_size,
        tool_name="get_transactions_by_address",
        next_call_base_params={
            "chain_id": chain_id,
            "address": address,
            "age_from": age_from,
            "age_to": age_to,
            "methods": methods,
        },
        cursor_extractor=extract_advanced_filters_cursor_params,
        force_pagination=has_more_pages and len(filtered_items) <= config.advanced_filters_page_size,
    )
    transformed_items = [
        AdvancedFilterItem.model_validate(
            _transform_advanced_filter_item(item, fields_to_remove)
        )
        for item in final_items
    ]

    return build_tool_response(data=transformed_items, pagination=pagination)
