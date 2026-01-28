"""Specialized handler for processing transaction summary responses."""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context

from blockscout_mcp_server.models import ToolResponse, TransactionSummaryData
from blockscout_mcp_server.tools.common import build_tool_response
from blockscout_mcp_server.tools.direct_api.dispatcher import register_handler


@register_handler(r"^/api/v2/transactions/(?P<transaction_hash>0x[a-fA-F0-9]{64})/summary/?$")
async def handle_transaction_summary(
    *,
    match: re.Match[str],
    response_json: dict[str, Any],
    query_params: dict[str, Any] | None = None,  # noqa: ARG001 - not used by this endpoint but required by dispatcher
    chain_id: str,  # noqa: ARG001 - reserved for future use in handlers
    base_url: str,  # noqa: ARG001 - reserved for future use in handlers
    ctx: Context,  # noqa: ARG001 - reserved for future use in handlers
) -> ToolResponse[TransactionSummaryData]:
    """Process the raw JSON response for a transaction summary request."""
    _ = match.group("transaction_hash")

    if response_json is None or response_json == {}:
        return build_tool_response(
            data=TransactionSummaryData(summary=None),
            notes=["No summary available. This usually indicates the transaction failed."],
        )

    if not isinstance(response_json, dict):
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")
    data = response_json.get("data")
    if not isinstance(data, dict) or "summaries" not in data:
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")

    summary = data.get("summaries")
    if summary is None or not isinstance(summary, list):
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")

    summary_data = TransactionSummaryData(summary=summary)

    return build_tool_response(data=summary_data)
