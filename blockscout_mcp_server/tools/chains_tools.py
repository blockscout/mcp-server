from mcp.server.fastmcp import Context

from blockscout_mcp_server.cache import find_blockscout_url
from blockscout_mcp_server.models import ChainInfo, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    chain_cache,
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

    response_data = await make_chainscout_request(api_path=api_path)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Successfully fetched chains list.",
    )

    chains: list[ChainInfo] = []
    if isinstance(response_data, dict):
        filtered: dict[str, dict] = {}
        for chain_id, chain in response_data.items():
            if not isinstance(chain, dict):
                continue
            if find_blockscout_url(chain):
                filtered[chain_id] = chain

        chain_cache.bulk_set(filtered)

        for chain_id, chain in filtered.items():
            if chain.get("name"):
                chains.append(
                    ChainInfo(
                        name=chain["name"],
                        chain_id=chain_id,
                        # Chainscout /api/chains uses camelCase field names;
                        # map them defensively in case of schema changes.
                        is_testnet=chain.get("isTestnet", False),
                        native_currency=chain.get("nativeCurrency"),
                        ecosystem=chain.get("ecosystem"),
                    )
                )

    return build_tool_response(data=chains)
