from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import LatestBlockData, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def get_latest_block(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")], ctx: Context
) -> ToolResponse[LatestBlockData]:
    """
    Get the latest indexed block number and timestamp, which represents the most recent state of the blockchain.
    No transactions or token transfers can exist beyond this point, making it useful as a reference timestamp for other API calls.
    """  # noqa: E501
    api_path = "/api/v2/main-page/blocks"

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch latest block info on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Resolved Blockscout instance URL. Fetching latest block data...",
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Successfully fetched latest block data.",
    )

    # The API returns a list. Extract data from the first item
    if response_data and isinstance(response_data, list) and len(response_data) > 0:
        first_block = response_data[0]
        # The main idea of this tool is to provide the latest block number of the chain.
        # The timestamp is provided to be used as a reference timestamp for other API calls.
        block_data = LatestBlockData(
            block_number=first_block.get("height"),
            timestamp=first_block.get("timestamp"),
        )
        return build_tool_response(data=block_data)

    # Handle cases with no data by raising an error
    raise ValueError("Could not retrieve latest block data from the API.")
