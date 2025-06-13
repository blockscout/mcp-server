import pytest

import json
from blockscout_mcp_server.tools.transaction_tools import transaction_summary, get_transaction_logs


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_summary_integration(mock_ctx):
    """Tests transaction_summary against a stable, historical transaction to ensure
    the 'summaries' field is correctly extracted from the 'data' object."""
    # A stable, historical transaction (e.g., an early Uniswap V2 router transaction)
    tx_hash = "0x5c7f2f244d91ec281c738393da0be6a38bc9045e29c0566da8c11e7a2f7cbc64"
    result = await transaction_summary(chain_id="1", hash=tx_hash, ctx=mock_ctx)

    # Assert that the result is a non-empty string
    assert isinstance(result, str)
    assert len(result) > 0

    # Assert that the tool's formatting prefix is present. This confirms
    # that the tool successfully extracted the summary data and proceeded
    # with formatting, rather than returning "No summary available."
    assert "# Transaction Summary from Blockscout Transaction Interpreter" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_logs_integration(mock_ctx):
    """Tests that get_transaction_logs correctly transforms a live API response for a transaction with a known number of logs."""
    # This transaction is stable and known to have exactly 2 log entries.
    tx_hash = "0xf1ad28f8d821b07cffe8d3f6adb737875e5e018b0eb9e7c0774bf3d60c747241"
    result_str = await get_transaction_logs(chain_id="1", hash=tx_hash, ctx=mock_ctx)

    assert isinstance(result_str, str)
    assert "**Items Structure:**" in result_str
    assert "**Transaction logs JSON:**" in result_str

    json_part = result_str.split("**Transaction logs JSON:**\n")[-1]
    data = json.loads(json_part)

    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2, "Expected exactly 2 log items for this transaction"
    assert data.get("next_page_params") is None, "Expected no pagination for this response"

    first_log = data["items"][0]
    assert "address" in first_log and isinstance(first_log["address"], str)
    assert "block_number" in first_log and isinstance(first_log["block_number"], int)
    assert "transaction_hash" not in first_log
    assert "block_hash" not in first_log

