from typing import Annotated
from pydantic import Field
from blockscout_mcp_server.tools.common import (
    make_bens_request,
    report_and_log_progress,
)
from mcp.server.fastmcp import Context


async def get_address_by_ens_name(
    name: Annotated[str, Field(description="ENS domain name to resolve")],
    ctx: Context
) -> dict:
    """
    Useful for when you need to convert an ENS domain name (e.g. "blockscout.eth")
    to its corresponding Ethereum address.
    """
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

    # Extract data as per responseTemplate: {"resolved_address": "{{.resolved_address.hash}}"}
    resolved_address_info = response_data.get("resolved_address", {})
    address_hash = resolved_address_info.get("hash")

    return {"resolved_address": address_hash} 