# SPDX-License-Identifier: LicenseRef-Blockscout
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import TokenSearchResult, ToolResponse
from blockscout_mcp_server.pro_api_key_context import pro_api_credit_scope, pro_api_key_scope
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation

# Maximum number of token results returned by lookup_token_by_symbol
TOKEN_RESULTS_LIMIT = 7


@log_tool_invocation
@pro_api_key_scope
@pro_api_credit_scope
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

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message=f"Starting token search for '{symbol}' on chain {chain_id}...",
    )

    response_data = await make_blockscout_request(
        chain_id=chain_id,
        api_path=api_path,
        params=params,
        timeout=config.bs_light_timeout,
    )

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
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

    search_results = [
        TokenSearchResult(
            address=item.get("address_hash", ""),
            name=item.get("name", ""),
            symbol=item.get("symbol", ""),
            token_type=item.get("token_type", ""),
            total_supply=item.get("total_supply"),
            circulating_market_cap=item.get("circulating_market_cap"),
            exchange_rate=item.get("exchange_rate"),
            is_smart_contract_verified=item.get("is_smart_contract_verified", False),
            is_verified_via_admin_panel=item.get("is_verified_via_admin_panel", False),
        )
        for item in items_to_process
    ]

    content_text = f'Found {len(search_results)} tokens matching "{symbol}" on chain {chain_id}.'
    if len(all_items) > TOKEN_RESULTS_LIMIT:
        content_text = f'Showing top {len(search_results)} of more tokens matching "{symbol}" on chain {chain_id}.'

    return build_tool_response(data=search_results, notes=notes, content_text=content_text)
