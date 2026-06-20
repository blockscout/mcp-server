# SPDX-License-Identifier: LicenseRef-Blockscout
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
from blockscout_mcp_server.pro_api_key_context import pro_api_credit_scope, pro_api_key_scope
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    extract_advanced_filters_cursor_params,
    make_blockscout_request,
    make_request_with_periodic_progress,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.tools.transaction._shared import _transform_advanced_filter_item


@log_tool_invocation
@pro_api_key_scope
@pro_api_credit_scope
async def get_token_transfers_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either transfer initiator or transfer receiver")],
    ctx: Context,
    age_from: Annotated[
        str,
        Field(
            description=(
                "Start date and time (e.g 2025-05-22T23:00:00.00Z). "
                "Alone, returns all ERC-20 transfers to/from the address since this date."
            )
        ),
    ],
    age_to: Annotated[
        str | None,
        Field(
            description=(
                "End date and time (e.g 2025-05-22T22:30:00.00Z). "
                "Adding this bounds the upper end of the date range started by `age_from`."
            )
        ),
    ] = None,
    token: Annotated[
        str | None,
        Field(
            description=(
                "An ERC-20 token contract address to restrict results to a single token. "
                "If omitted, returns transfers of all tokens."
            )
        ),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[AdvancedFilterItem]]:
    """
    Get ERC-20 token transfers for an address within a specific time range.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "transaction_types": "ERC-20",
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address,
        "age_from": age_from,
    }

    if age_to:
        query_params["age_to"] = age_to
    if token:
        query_params["token_contract_address_hashes_to_include"] = token

    apply_cursor_to_params(cursor, query_params)

    tool_overall_total_steps = 1.0

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=tool_overall_total_steps,
        message=f"Starting to fetch token transfers for {address} on chain {chain_id}...",
    )

    response_data = await make_request_with_periodic_progress(
        ctx=ctx,
        request_function=make_blockscout_request,
        request_args={"chain_id": chain_id, "api_path": api_path, "params": query_params},
        total_duration_hint=config.bs_timeout,
        progress_interval_seconds=config.progress_interval_seconds,
        in_progress_message_template="Query in progress... ({elapsed_seconds:.0f}s / {total_hint:.0f}s hint)",
        tool_overall_total_steps=tool_overall_total_steps,
        current_step_number=1.0,
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
        AdvancedFilterItem.model_validate(_transform_advanced_filter_item(item, fields_to_remove))
        for item in sliced_items
    ]

    range_text = f"from {age_from}" if age_to is None else f"from {age_from} to {age_to}"
    content_text = f"Found {len(transformed_items)} token transfers for {address} on chain {chain_id} {range_text}."
    if pagination is not None:
        content_text = (
            f"Returned {len(transformed_items)} token transfers for {address} on chain {chain_id} {range_text}. "
            "More pages available."
        )

    return build_tool_response(data=transformed_items, pagination=pagination, content_text=content_text)
