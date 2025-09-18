from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import (
    NextCallInfo,
    PaginationInfo,
    TokenHoldingData,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    encode_cursor,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


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
    params = {"type": "ERC-20"}

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
        decimals_value = token.get("decimals")
        total_supply_value = token.get("total_supply")
        circulating_market_cap_value = token.get("circulating_market_cap")
        exchange_rate_value = token.get("exchange_rate")
        holders_count_value = token.get("holders_count")
        balance_value = item.get("value")
        token_holdings.append(
            TokenHoldingData(
                address=token.get("address_hash", ""),
                name=token.get("name") or "",
                symbol=token.get("symbol") or "",
                decimals="" if decimals_value is None else str(decimals_value),
                total_supply="" if total_supply_value is None else str(total_supply_value),
                circulating_market_cap=(
                    None
                    if circulating_market_cap_value is None
                    else str(circulating_market_cap_value)
                ),
                exchange_rate=None if exchange_rate_value is None else str(exchange_rate_value),
                holders_count="" if holders_count_value is None else str(holders_count_value),
                balance="" if balance_value is None else str(balance_value),
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
