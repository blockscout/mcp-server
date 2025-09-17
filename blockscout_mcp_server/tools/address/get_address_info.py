import asyncio
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import (
    AddressInfoData,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    make_metadata_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def get_address_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address to get information about")],
    ctx: Context,
) -> ToolResponse[AddressInfoData]:
    """
    Get comprehensive information about an address, including:
    - Address existence check
    - Native token (ETH) balance (provided as is, without adjusting by decimals)
    - ENS name association (if any)
    - Contract status (whether the address is a contract, whether it is verified)
    - Proxy contract information (if applicable): determines if a smart contract is a proxy contract (which forwards calls to implementation contracts), including proxy type and implementation addresses
    - Token details (if the contract is a token): name, symbol, decimals, total supply, etc.
    Essential for address analysis, contract investigation, token research, and DeFi protocol analysis.
    """  # noqa: E501
    await report_and_log_progress(
        ctx, progress=0.0, total=3.0, message=f"Starting to fetch address info for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)
    await report_and_log_progress(
        ctx, progress=1.0, total=3.0, message="Resolved Blockscout instance URL. Fetching data..."
    )

    blockscout_api_path = f"/api/v2/addresses/{address}"
    metadata_api_path = "/api/v1/metadata"
    metadata_params = {"addresses": address, "chainId": chain_id}

    address_info_result, metadata_result = await asyncio.gather(
        make_blockscout_request(base_url=base_url, api_path=blockscout_api_path),
        make_metadata_request(api_path=metadata_api_path, params=metadata_params),
        return_exceptions=True,
    )

    if isinstance(address_info_result, Exception):
        raise address_info_result

    await report_and_log_progress(ctx, progress=2.0, total=3.0, message="Fetched basic address info.")

    notes = None
    if isinstance(metadata_result, Exception):
        notes = [f"Could not retrieve address metadata. The 'metadata' field is null. Error: {metadata_result}"]
        metadata_data = None
    elif metadata_result.get("addresses"):
        address_key = next(
            (key for key in metadata_result["addresses"] if key.lower() == address.lower()),
            None,
        )
        metadata_data = metadata_result["addresses"].get(address_key) if address_key else None
    else:
        metadata_data = None

    address_data = AddressInfoData(basic_info=address_info_result, metadata=metadata_data)

    await report_and_log_progress(ctx, progress=3.0, total=3.0, message="Successfully fetched all address data.")
    instructions = [
        (f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/logs` to get Logs Emitted by Address."),
        (
            f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/coin-balance-history-by-day` "
            "to get daily native coin balance history."
        ),
        (
            f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/coin-balance-history` "
            "to get native coin balance history."
        ),
        (
            f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/blocks-validated` "
            "to get Blocks Validated by this Address."
        ),
        (
            f"Use `direct_api_call` with endpoint `/api/v2/proxy/account-abstraction/accounts/{address}` "
            "to get Account Abstraction info."
        ),
        (
            f"Use `direct_api_call` with endpoint `/api/v2/proxy/account-abstraction/operations` "
            f"and query_params={{'sender': '{address}'}} to get User Operations sent by this Address."
        ),
    ]

    return build_tool_response(data=address_data, notes=notes, instructions=instructions)
