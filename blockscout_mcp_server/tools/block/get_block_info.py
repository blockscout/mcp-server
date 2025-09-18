import asyncio
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import BlockInfoData, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def get_block_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    number_or_hash: Annotated[str, Field(description="Block number or hash")],
    ctx: Context,
    include_transactions: Annotated[
        bool | None, Field(description="If true, includes a list of transaction hashes from the block.")
    ] = False,
) -> ToolResponse[BlockInfoData]:
    """
    Get block information like timestamp, gas used, burnt fees, transaction count etc.
    Can optionally include the list of transaction hashes contained in the block. Transaction hashes are omitted by default; request them only when you truly need them, because on high-traffic chains the list may exhaust the context.
    """  # noqa: E501
    total_steps = 3.0 if include_transactions else 2.0

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=total_steps,
        message=f"Starting to fetch block info for {number_or_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=total_steps,
        message="Resolved Blockscout instance URL. Fetching block data...",
    )

    if not include_transactions:
        response_data = await make_blockscout_request(base_url=base_url, api_path=f"/api/v2/blocks/{number_or_hash}")
        await report_and_log_progress(
            ctx,
            progress=2.0,
            total=total_steps,
            message="Successfully fetched block data.",
        )
        block_data = BlockInfoData(block_details=response_data)
        return build_tool_response(data=block_data)

    block_api_path = f"/api/v2/blocks/{number_or_hash}"
    txs_api_path = f"/api/v2/blocks/{number_or_hash}/transactions"

    results = await asyncio.gather(
        make_blockscout_request(base_url=base_url, api_path=block_api_path),
        make_blockscout_request(base_url=base_url, api_path=txs_api_path),
        return_exceptions=True,
    )
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=total_steps,
        message="Fetched block and transaction data.",
    )

    block_info_result, txs_result = results
    notes = None

    if isinstance(block_info_result, Exception):
        raise block_info_result

    tx_hashes = None
    if isinstance(txs_result, Exception):
        notes = [f"Could not retrieve the list of transactions for this block. Error: {txs_result}"]
    else:
        tx_items = txs_result.get("items", [])
        tx_hashes = [tx.get("hash") for tx in tx_items if tx.get("hash")]

    await report_and_log_progress(
        ctx,
        progress=3.0,
        total=total_steps,
        message="Successfully fetched all block data.",
    )

    # The block details are added to the response as they are returned by the API.
    # Where as for transactions only the hashes are added. AI agents can use the hashes
    # to get the full transaction details using the `get_transaction_info` tool.
    block_data = BlockInfoData(block_details=block_info_result, transaction_hashes=tx_hashes)
    return build_tool_response(data=block_data, notes=notes)
