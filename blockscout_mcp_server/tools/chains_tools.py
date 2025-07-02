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
        # 1. No need to sort the chains as per the nature of Chainscout: most popular chains are at the top
        # 2. The chain ID can be either numeric or string, so we don't need to convert it to int
        chains.extend(
            ChainInfo(name=item["name"], chain_id=item["chainid"])
            for item in response_data
            if item.get("name") and item.get("chainid")
        )

    return build_tool_response(data=chains)
