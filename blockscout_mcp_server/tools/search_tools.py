from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import TokenSearchResult, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    log_tool_invocation,
    make_blockscout_request,
    report_and_log_progress,
)

# Maximum number of token results returned by lookup_token_by_symbol
TOKEN_RESULTS_LIMIT = 7


@log_tool_invocation
async def lookup_token_by_symbol(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    symbol: Annotated[str, Field(description="Token symbol or name to search for")],
    ctx: Context,
) -> ToolResponse[list[TokenSearchResult]]:
    """
    Search for token addresses by symbol or name. Returns multiple potential
    matches based on symbol or token name similarity. Only the first
    ``TOKEN_RESULTS_LIMIT`` matches from the Blockscout API are returned.
    """
    api_path = "/api/v2/search"
    params = {"q": symbol}

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting token search for '{symbol}' on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Resolved Blockscout instance URL. Searching for tokens...",
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Successfully completed token search.",
    )

    all_items = response_data.get("items", [])
    notes = None

    if len(all_items) > TOKEN_RESULTS_LIMIT:
        notes = [
            (
                f"The number of results exceeds the limit of {TOKEN_RESULTS_LIMIT}. "
                f"Only the first {TOKEN_RESULTS_LIMIT} are shown."
            )
        ]

    items_to_process = all_items[:TOKEN_RESULTS_LIMIT]

    # To preserve the LLM context, only specific fields are added to the response
    search_results = [
        TokenSearchResult(
            address=item.get("address_hash", ""),
            name=item.get("name", ""),
            symbol=item.get("symbol", ""),
            token_type=item.get("token_type", ""),
            total_supply=item.get("total_supply", ""),
            circulating_market_cap=item.get("circulating_market_cap"),
            exchange_rate=item.get("exchange_rate"),
            is_smart_contract_verified=item.get("is_smart_contract_verified", False),
            is_verified_via_admin_panel=item.get("is_verified_via_admin_panel", False),
        )
        for item in items_to_process
    ]

    return build_tool_response(data=search_results, notes=notes)
