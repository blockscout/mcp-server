from datetime import UTC, datetime
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import LatestBlockData, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


def _parse_datetime_to_timestamp(value: str) -> int:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Invalid datetime format. Expected ISO 8601 string.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


@log_tool_invocation
async def get_block_number(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    ctx: Context,
    datetime: Annotated[
        str | None,
        Field(
            description=(
                "The date and time (ISO 8601 format, e.g. 2025-05-22T23:00:00.00Z) "
                "to find the block for. If omitted, returns the latest block."
            )
        ),
    ] = None,
) -> ToolResponse[LatestBlockData]:
    """
    Retrieves the block number and timestamp for a specific date/time or the latest block.
    Use when you need a block height for a specific point in time (e.g., "block at 2024-01-01")
    or the current chain tip. If `datetime` is provided, finds the block immediately
    preceding that time. If omitted, returns the latest indexed block.
    """
    if datetime is None:
        await report_and_log_progress(
            ctx,
            progress=0.0,
            total=2.0,
            message=f"Starting to fetch latest block info on chain {chain_id}...",
        )

        base_url = await get_blockscout_base_url(chain_id)

        await report_and_log_progress(
            ctx,
            progress=1.0,
            total=2.0,
            message="Resolved Blockscout instance URL. Fetching latest block data...",
        )

        response_data = await make_blockscout_request(base_url=base_url, api_path="/api/v2/main-page/blocks")

        await report_and_log_progress(
            ctx,
            progress=2.0,
            total=2.0,
            message="Successfully fetched latest block data.",
        )

        if response_data and isinstance(response_data, list) and len(response_data) > 0:
            first_block = response_data[0]
            block_number = first_block.get("height")
            timestamp = first_block.get("timestamp")
            if block_number is None or timestamp is None:
                raise ValueError("Blockscout API returned an incomplete latest block response.")
            block_data = LatestBlockData(block_number=int(block_number), timestamp=timestamp)
            return build_tool_response(data=block_data)

        raise ValueError("Could not retrieve latest block data from the API.")

    timestamp_value = _parse_datetime_to_timestamp(datetime)

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=3.0,
        message=f"Starting to resolve block number on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=3.0,
        message="Resolved Blockscout instance URL. Finding block by time...",
    )

    block_lookup = await make_blockscout_request(
        base_url=base_url,
        api_path="/api",
        params={
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": timestamp_value,
            "closest": "before",
        },
    )

    if block_lookup.get("status") != "1":
        message = block_lookup.get("message") or block_lookup.get("result") or "Unknown error"
        raise ValueError(f"Blockscout API error while resolving block by time: {message}")

    block_number_value = block_lookup.get("result")
    if isinstance(block_number_value, dict):
        block_number_value = block_number_value.get("blockNumber") or block_number_value.get("block_number")
    if block_number_value is None:
        raise ValueError("Blockscout API did not return a block number.")

    try:
        block_number_int = int(block_number_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Blockscout API returned a non-integer block number.") from exc

    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=3.0,
        message="Resolved block number. Fetching block timestamp...",
    )

    block_details = await make_blockscout_request(
        base_url=base_url,
        api_path=f"/api/v2/blocks/{block_number_int}",
    )

    block_timestamp = block_details.get("timestamp")
    if block_timestamp is None:
        raise ValueError("Blockscout API did not return a timestamp for the resolved block.")

    await report_and_log_progress(
        ctx,
        progress=3.0,
        total=3.0,
        message="Successfully resolved block number by time.",
    )

    block_data = LatestBlockData(block_number=block_number_int, timestamp=block_timestamp)
    return build_tool_response(data=block_data)
