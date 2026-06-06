# SPDX-License-Identifier: LicenseRef-Blockscout
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import ChainInfo, ToolResponse
from blockscout_mcp_server.pro_api_key_context import pro_api_credit_scope, pro_api_key_scope
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    chains_list_cache,
    ensure_pro_api_config,
    make_chainscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
@pro_api_key_scope
@pro_api_credit_scope
async def get_chains_list(
    ctx: Context,
    query: Annotated[
        str | None,
        Field(
            description=(
                "Optional case-insensitive substring filter applied to chain name, chain ID, "
                "native currency, and ecosystem. Prefer narrow text terms over partial numeric "
                "chain IDs because matching is substring-based."
            )
        ),
    ] = None,
) -> ToolResponse[list[ChainInfo]]:
    """Get supported blockchain chains with their chain IDs.

    Use this when another tool needs a supported `chain_id` and only the chain name,
    ecosystem, or native currency is known. Prefer a narrow `query` to avoid returning
    the full registry to the agent. Do not rely on partial numeric chain ID queries such
    as `1`, because matching is substring-based and may return many chains.
    """
    api_path = "/api/chains"

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message="Fetching chains list...",
    )

    chains = chains_list_cache.get_if_fresh()
    from_cache = True

    if chains is None:
        from_cache = False
        async with chains_list_cache.lock:
            chains = chains_list_cache.get_if_fresh()
            if chains is None:
                pro_api_chains = await ensure_pro_api_config()
                response_data = await make_chainscout_request(api_path=api_path)

                chains = []
                if isinstance(response_data, dict):
                    for chain_id in pro_api_chains:
                        chain = response_data.get(chain_id)
                        if not isinstance(chain, dict) or not chain.get("name"):
                            continue
                        chains.append(
                            ChainInfo(
                                name=chain["name"],
                                chain_id=chain_id,
                                is_testnet=chain.get("isTestnet", False),
                                native_currency=chain.get("native_currency"),
                                ecosystem=chain.get("ecosystem"),
                                settlement_layer_chain_id=chain.get("settlementLayerChainId"),
                            )
                        )

                if chains:
                    chains_list_cache.store_snapshot(chains)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Successfully fetched chains list." if not from_cache else "Chains list returned from cache.",
    )

    chains = chains or []
    normalized_query = query.strip().lower() if query and query.strip() else None

    if normalized_query:
        filtered_chains = []
        for chain in chains:
            ecosystem = chain.ecosystem
            ecosystem_matches = False
            if isinstance(ecosystem, str):
                ecosystem_matches = normalized_query in ecosystem.lower()
            elif isinstance(ecosystem, list):
                ecosystem_matches = any(normalized_query in item.lower() for item in ecosystem)

            if (
                normalized_query in chain.name.lower()
                or normalized_query in chain.chain_id.lower()
                or (chain.native_currency and normalized_query in chain.native_currency.lower())
                or ecosystem_matches
            ):
                filtered_chains.append(chain)

        content_text = f"Retrieved {len(filtered_chains)} chains matching '{query.strip()}' ({len(chains)} total)."
        notes = None
        if not filtered_chains:
            notes = [
                (
                    f"No chains matched query '{query.strip()}'. Try a broader term or omit "
                    "the query parameter to see all chains."
                )
            ]
        return build_tool_response(data=filtered_chains, content_text=content_text, notes=notes)

    content_text = f"Retrieved {len(chains)} supported blockchain chains."
    return build_tool_response(data=chains, content_text=content_text)
