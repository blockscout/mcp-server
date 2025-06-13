import pytest

import json
import httpx
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
    """Tests that get_transaction_logs returns a pagination hint for a multi-page response."""
    tx_hash = "0x293b638403324a2244a8245e41b3b145e888a26e3a51353513030034a26a4e41"
    try:
        result_str = await get_transaction_logs(chain_id="1", hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Transaction unavailable: {e}")

    assert isinstance(result_str, str)
    assert "**Transaction logs JSON:**" in result_str
    assert "To get the next page call" in result_str
    assert 'cursor="' in result_str

    json_part = result_str.split("----")[0]
    data = json.loads(json_part.split("**Transaction logs JSON:**\n")[-1])

    assert "items" in data
    assert len(data["items"]) > 0

