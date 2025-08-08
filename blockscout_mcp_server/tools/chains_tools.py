from mcp.server.fastmcp import Context

from blockscout_mcp_server.models import ChainInfo, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    chain_cache,
    chains_list_cache,
    find_blockscout_url,
    make_chainscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def get_chains_list(ctx: Context) -> ToolResponse[list[ChainInfo]]:
    """
    Get the list of known blockchain chains with their IDs.
    Useful for getting a chain ID when the chain name is known. This information can be used in other tools that require a chain ID to request information.
    """  # noqa: E501
    api_path = "/api/chains"

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message="Fetching chains list from Chainscout...",
    )

    chains = chains_list_cache.get_if_fresh()
    from_cache = True

    if chains is None:
        from_cache = False
        async with chains_list_cache.lock:
            chains = chains_list_cache.get_if_fresh()
            if chains is None:
                response_data = await make_chainscout_request(api_path=api_path)

                chains = []
                if isinstance(response_data, dict):
                    filtered: dict[str, dict] = {}
                    url_map: dict[str, str] = {}
                    for chain_id, chain in response_data.items():
                        if not isinstance(chain, dict):
                            continue
                        url = find_blockscout_url(chain)
                        if url:
                            filtered[chain_id] = chain
                            url_map[chain_id] = url

                    await chain_cache.bulk_set(url_map)

                    for chain_id, chain in filtered.items():
                        if chain.get("name"):
                            chains.append(
                                ChainInfo(
                                    name=chain["name"],
                                    chain_id=chain_id,
                                    # Fields follow the Chainscout API schema (isTestnet, native_currency)
                                    is_testnet=chain.get("isTestnet", False),
                                    native_currency=chain.get("native_currency"),
                                    ecosystem=chain.get("ecosystem"),
                                )
                            )

                    chains_list_cache.store_snapshot(chains)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Successfully fetched chains list." if not from_cache else "Chains list returned from cache.",
    )

    return build_tool_response(data=chains or [])
