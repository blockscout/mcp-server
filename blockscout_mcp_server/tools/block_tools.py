from typing import Annotated, Dict, Optional
import asyncio
import json
from pydantic import Field
from blockscout_mcp_server.tools.common import (
    make_blockscout_request,
    get_blockscout_base_url,
    report_and_log_progress,
)
from mcp.server.fastmcp import Context

async def get_block_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    number_or_hash: Annotated[str, Field(description="Block number or hash")],
    ctx: Context,
    include_transactions: Annotated[Optional[bool], Field(description="If true, includes a list of transaction hashes from the block.")] = False
) -> str:
    """
    Get block information like timestamp, gas used, burnt fees, transaction count etc.
    Can optionally include the list of transaction hashes contained in the block. Transaction hashes are omitted by default; request them only when you truly need them, because on high-traffic chains the list may exhaust the context.
    """
    total_steps = 3.0 if include_transactions else 2.0

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=total_steps,
        message=f"Starting to fetch block info for {number_or_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=total_steps,
        message="Resolved Blockscout instance URL. Fetching block data...",
    )

    if not include_transactions:
        response_data = await make_blockscout_request(
            base_url=base_url,
            api_path=f"/api/v2/blocks/{number_or_hash}"
        )
        await report_and_log_progress(
            ctx,
            progress=2.0,
            total=total_steps,
            message="Successfully fetched block data.",
        )
        return f"Basic block info:\n{json.dumps(response_data)}"

    # If include_transactions is True
    block_api_path = f"/api/v2/blocks/{number_or_hash}"
    txs_api_path = f"/api/v2/blocks/{number_or_hash}/transactions"

    # We use asyncio.gather to run both API requests concurrently.
    # return_exceptions=True ensures that if one call fails, the other can still complete.
    results = await asyncio.gather(
        make_blockscout_request(base_url=base_url, api_path=block_api_path),
        make_blockscout_request(base_url=base_url, api_path=txs_api_path),
        return_exceptions=True
    )
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=total_steps,
        message="Fetched block and transaction data.",
    )

    block_info_result, txs_result = results
    output_parts = []

    # First, handle the result of the main block info call.
    if isinstance(block_info_result, Exception):
        return f"Error fetching basic block info: {block_info_result}"

    output_parts.append("Basic block info:")
    output_parts.append(json.dumps(block_info_result))

    # Second, handle the result of the transactions call.
    if isinstance(txs_result, Exception):
        output_parts.append(f"\n\nError fetching transactions for the block: {txs_result}")
    else:
        # The API returns transactions inside an "items" list.
        tx_items = txs_result.get("items", [])
        if tx_items:
            # We only need the 'hash' from each transaction object.
            tx_hashes = [tx.get("hash") for tx in tx_items if tx.get("hash")]
            output_parts.append("\n\nTransactions in the block:")
            output_parts.append(json.dumps(tx_hashes))
        else:
            # Handle the case where the block has no transactions.
            output_parts.append("\n\nNo transactions in the block.")

    await report_and_log_progress(
        ctx,
        progress=3.0,
        total=total_steps,
        message="Successfully fetched all block data.",
    )
    return "\n".join(output_parts)

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
    
    # The API returns a list. Extract data from the first item as per responseTemplate
    if response_data and isinstance(response_data, list) and len(response_data) > 0:
        first_block = response_data[0]
        return {
            "block_number": first_block.get("height"),
            "timestamp": first_block.get("timestamp")
        }
    
    # Return empty values if no data is available
    return {"block_number": None, "timestamp": None} 