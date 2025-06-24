from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.tools.common import (
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)


async def get_contract_abi(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Smart contract address")],
    ctx: Context,
) -> dict:
    """
    Get smart contract ABI (Application Binary Interface).
    An ABI defines all functions, events, their parameters, and return types. The ABI is required to format function calls or interpret contract data.
    """  # noqa: E501
    api_path = f"/api/v2/smart-contracts/{address}"

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch contract ABI for {address} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Resolved Blockscout instance URL. Fetching contract ABI...",
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Successfully fetched contract ABI.",
    )

    # Extract the ABI from the response as per responseTemplate: {"abi": "{{.abi}}"}
    return {"abi": response_data.get("abi")}
