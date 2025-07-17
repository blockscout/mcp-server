from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import EnsAddressData, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    make_bens_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def get_address_by_ens_name(
    name: Annotated[str, Field(description="ENS domain name to resolve")], ctx: Context
) -> ToolResponse[EnsAddressData]:
    """
    Useful for when you need to convert an ENS domain name (e.g. "blockscout.eth")
    to its corresponding Ethereum address.
    """
    # TODO: add support for other chains
    api_path = f"/api/v1/1/domains/{name}"

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message=f"Resolving ENS name {name}...",
    )

    response_data = await make_bens_request(api_path=api_path)

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message=f"Successfully resolved ENS name {name}.",
    )

    # Only the address hash is added to the response
    resolved_address_info = response_data.get("resolved_address", {})
    address_hash = resolved_address_info.get("hash") if resolved_address_info else None
    ens_data = EnsAddressData(resolved_address=address_hash)

    return build_tool_response(data=ens_data)
