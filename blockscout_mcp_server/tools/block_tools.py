from typing import Annotated, Dict
from pydantic import Field
from blockscout_mcp_server.tools.common import make_blockscout_request, get_blockscout_base_url
from mcp.server.fastmcp import Context

async def get_block_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    number_or_hash: Annotated[str, Field(description="Block number or hash")],
    ctx: Context
) -> Dict:
    """
    Get block information like timestamp, gas used, burnt fees, transaction count etc.
    """
    api_path = f"/api/v2/blocks/{number_or_hash}"
    
    # Report start of operation
    await ctx.report_progress(progress=0.0, total=2.0, message=f"Starting to fetch block info for {number_or_hash} on chain {chain_id}...")
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await ctx.report_progress(progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching block data...")
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)
    
    # Report completion
    await ctx.report_progress(progress=2.0, total=2.0, message="Successfully fetched block data.")
    
    return response_data

async def get_latest_block(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    ctx: Context
) -> Dict:
    """
    Get the latest indexed block number and timestamp, which represents the most recent state of the blockchain. 
    No transactions or token transfers can exist beyond this point, making it useful as a reference timestamp for other API calls.
    """
    api_path = "/api/v2/main-page/blocks"
    
    # Report start of operation
    await ctx.report_progress(progress=0.0, total=2.0, message=f"Starting to fetch latest block info on chain {chain_id}...")
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await ctx.report_progress(progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching latest block data...")
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)
    
    # Report completion
    await ctx.report_progress(progress=2.0, total=2.0, message="Successfully fetched latest block data.")
    
    # The API returns a list. Extract data from the first item as per responseTemplate
    if response_data and isinstance(response_data, list) and len(response_data) > 0:
        first_block = response_data[0]
        return {
            "block_number": first_block.get("height"),
            "timestamp": first_block.get("timestamp")
        }
    
    # Return empty values if no data is available
    return {"block_number": None, "timestamp": None} 