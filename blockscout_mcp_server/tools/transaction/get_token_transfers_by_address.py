from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    extract_advanced_filters_cursor_params,
    get_blockscout_base_url,
    make_blockscout_request,
    make_request_with_periodic_progress,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.tools.transaction._shared import _transform_advanced_filter_item


@log_tool_invocation
async def get_token_transfers_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either transfer initiator or transfer receiver")],
    ctx: Context,
    age_from: Annotated[
        str | None,
        Field(
            description="Start date and time (e.g 2025-05-22T23:00:00.00Z). This parameter should be provided in most cases to limit transfers and avoid heavy database queries. Omit only if you absolutely need the full history."  # noqa: E501
        ),
    ] = None,
    age_to: Annotated[
        str | None,
        Field(
            description="End date and time (e.g 2025-05-22T22:30:00.00Z). Can be omitted to get all transfers up to the current time."  # noqa: E501
        ),
    ] = None,
    token: Annotated[
        str | None,
        Field(
            description="An ERC-20 token contract address to filter transfers by a specific token. If omitted, returns transfers of all tokens."  # noqa: E501
        ),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[AdvancedFilterItem]]:
    """
    Get ERC-20 token transfers for an address within a specific time range.
    Use cases:
      - `get_token_transfers_by_address(address, age_from)` - get all transfers of any ERC-20 token to/from the address since the given date up to the current time
      - `get_token_transfers_by_address(address, age_from, age_to)` - get all transfers of any ERC-20 token to/from the address between the given dates
      - `get_token_transfers_by_address(address, age_from, age_to, token)` - get all transfers of the given ERC-20 token to/from the address between the given dates
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "transaction_types": "ERC-20",
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address,
    }

    if age_from:
        query_params["age_from"] = age_from
    if age_to:
        query_params["age_to"] = age_to
    if token:
        query_params["token_contract_address_hashes_to_include"] = token

    apply_cursor_to_params(cursor, query_params)

    tool_overall_total_steps = 2.0

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=tool_overall_total_steps,
        message=f"Starting to fetch token transfers for {address} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=tool_overall_total_steps,
        message="Resolved Blockscout instance URL. Now fetching token transfers...",
    )

    response_data = await make_request_with_periodic_progress(
        ctx=ctx,
        request_function=make_blockscout_request,
        request_args={"base_url": base_url, "api_path": api_path, "params": query_params},
        total_duration_hint=config.bs_timeout,
        progress_interval_seconds=config.progress_interval_seconds,
        in_progress_message_template="Query in progress... ({elapsed_seconds:.0f}s / {total_hint:.0f}s hint)",
        tool_overall_total_steps=tool_overall_total_steps,
        current_step_number=2.0,
        current_step_message_prefix="Fetching token transfers",
    )

    original_items = response_data.get("items", [])
    fields_to_remove = ["value", "internal_transaction_index", "created_contract"]

    sliced_items, pagination = create_items_pagination(
        items=original_items,
        page_size=config.advanced_filters_page_size,
        tool_name="get_token_transfers_by_address",
        next_call_base_params={
            "chain_id": chain_id,
            "address": address,
            "age_from": age_from,
            "age_to": age_to,
            "token": token,
        },
        cursor_extractor=extract_advanced_filters_cursor_params,
    )
    transformed_items = [
        AdvancedFilterItem.model_validate(
            _transform_advanced_filter_item(item, fields_to_remove)
        )
        for item in sliced_items
    ]

    return build_tool_response(data=transformed_items, pagination=pagination)
