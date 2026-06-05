# SPDX-License-Identifier: LicenseRef-Blockscout
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ContractAbiData, ToolResponse
from blockscout_mcp_server.pro_api_key_context import pro_api_key_scope
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
@pro_api_key_scope
async def get_contract_abi(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Smart contract address")],
    ctx: Context,
) -> ToolResponse[ContractAbiData]:
    """
    Get smart contract ABI (Application Binary Interface).
    An ABI defines all functions, events, their parameters, and return types. The ABI is required to format function calls or interpret contract data.
    """  # noqa: E501
    api_path = f"/api/v2/smart-contracts/{address}"

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message=f"Starting to fetch contract ABI for {address} on chain {chain_id}...",
    )

    # 20s light timeout validated empirically: payloads range from ~10 KB
    # (simple proxies) to ~350 KB (large multi-file projects like Uniswap V3
    # Universal Router); worst-case server response is ~10-15s on loaded
    # instances, leaving comfortable headroom under bs_light_timeout.
    response_data = await make_blockscout_request(
        chain_id=chain_id,
        api_path=api_path,
        timeout=config.bs_light_timeout,
    )

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Successfully fetched contract ABI.",
    )

    # Extract the ABI from the API response as it is
    abi_data = ContractAbiData(abi=response_data.get("abi"))

    abi_entries = abi_data.abi or []
    function_count = sum(1 for entry in abi_entries if isinstance(entry, dict) and entry.get("type") == "function")
    event_count = sum(1 for entry in abi_entries if isinstance(entry, dict) and entry.get("type") == "event")

    return build_tool_response(
        data=abi_data,
        content_text=(
            f"ABI for contract {address} on chain {chain_id}: {function_count} functions, {event_count} events."
        ),
    )
