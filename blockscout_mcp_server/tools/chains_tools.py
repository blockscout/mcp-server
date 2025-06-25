from mcp.server.fastmcp import Context

from blockscout_mcp_server.models import ChainInfo, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    make_chainscout_request,
    report_and_log_progress,
)


async def get_chains_list(ctx: Context) -> ToolResponse[list[ChainInfo]]:
    """
    Get the list of known blockchain chains with their IDs.
    Useful for getting a chain ID when the chain name is known. This information can be used in other tools that require a chain ID to request information.
    """  # noqa: E501
    api_path = "/api/chains/list"

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
    if isinstance(response_data, list):
        sorted_chains = sorted(response_data, key=lambda x: x.get("name", ""))
        for item in sorted_chains:
            if item.get("name") and item.get("chainid"):
                try:
                    chain_id = int(item["chainid"])
                except (TypeError, ValueError):
                    continue
                chains.append(ChainInfo(name=item["name"], chain_id=chain_id))

    return build_tool_response(data=chains)
