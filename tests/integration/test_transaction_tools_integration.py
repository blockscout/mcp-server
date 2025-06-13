import pytest

import json
from blockscout_mcp_server.tools.transaction_tools import transaction_summary, get_transaction_logs, get_transaction_info


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration(mock_ctx):
    """Tests that get_transaction_info returns full data and omits raw_input by default."""
    # This is a stable transaction with a known decoded input (a swap).
    tx_hash = "0xd4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    result = await get_transaction_info(chain_id="1", hash=tx_hash, ctx=mock_ctx)

    # Assert that the main data is present
    assert isinstance(result, dict)
    assert result["hash"].lower() == tx_hash.lower()
    assert result["status"] == "ok"
    assert "decoded_input" in result and result["decoded_input"] is not None

    # Assert that the raw_input is NOT present by default
    assert "raw_input" not in result

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration_no_decoded_input(mock_ctx):
    """Tests that get_transaction_info keeps raw_input by default when decoded_input is null."""
    # This is a stable contract creation transaction, which has no decoded_input.
    tx_hash = "0x12341be874149efc8c714f4ef431db0ce29f64532e5c70d3882257705e2b1ad2"
    result = await get_transaction_info(chain_id="1", hash=tx_hash, ctx=mock_ctx)

    # Assert that the main data is present
    assert isinstance(result, dict)
    assert result["hash"].lower() == tx_hash.lower()
    assert result["decoded_input"] is None

    # Assert that the raw_input IS present because decoded_input was null
    assert "raw_input" in result
    assert isinstance(result["raw_input"], str) and len(result["raw_input"]) > 2
