from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import ToolResponse, TransactionSummaryData
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def transaction_summary(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    transaction_hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
) -> ToolResponse[TransactionSummaryData]:
    """
    Get human-readable transaction summaries from Blockscout Transaction Interpreter.
    Automatically classifies transactions into natural language descriptions (transfers, swaps, NFT sales, DeFi operations)
    Essential for rapid transaction comprehension, dashboard displays, and initial analysis.
    Note: Not all transactions can be summarized and accuracy is not guaranteed for complex patterns.
    """  # noqa: E501
    api_path = f"/api/v2/transactions/{transaction_hash}/summary"

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch transaction summary for {transaction_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction summary..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction summary.")

    if not response_data:
        return build_tool_response(
            data=TransactionSummaryData(summary=None),
            notes=["No summary available. This usually indicates the transaction failed."],
        )

    data = response_data.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")

    if "summaries" not in data:
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")

    summary = data["summaries"]

    if not isinstance(summary, list):
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")

    summary_data = TransactionSummaryData(summary=summary)

    return build_tool_response(data=summary_data)
