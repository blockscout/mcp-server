import pytest

import json
import httpx
from blockscout_mcp_server.tools.transaction_tools import (
    transaction_summary,
    get_transaction_logs,
    get_transaction_info,
    get_transactions_by_address,
    get_token_transfers_by_address,
)


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
    """Tests that get_transaction_logs returns a paginated response and validates the schema."""
    # This transaction on Ethereum Mainnet is known to have many logs, ensuring a paginated response.
    tx_hash = "0x293b638403324a2244a8245e41b3b145e888a26e3a51353513030034a26a4e41"
    try:
        result_str = await get_transaction_logs(chain_id="1", hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Transaction data is currently unavailable from the API: {e}")

    # 1. Verify that pagination is working correctly
    assert isinstance(result_str, str)
    assert "To get the next page call" in result_str
    assert 'cursor="' in result_str
    assert "**Transaction logs JSON:**" in result_str

    # 2. Parse the JSON and verify the basic structure
    json_part = result_str.split("----")[0]
    data = json.loads(json_part.split("**Transaction logs JSON:**\n")[-1])
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0

    # 3. Validate the schema of the first transformed log item.
    first_log = data["items"][0]
    expected_keys = {"address", "block_number", "data", "decoded", "index", "topics"}
    assert set(first_log.keys()) == expected_keys

    # 4. Validate the data types of key fields.
    assert isinstance(first_log["address"], str)
    assert first_log["address"].startswith("0x")
    assert isinstance(first_log["block_number"], int)
    assert isinstance(first_log["index"], int)
    assert isinstance(first_log["topics"], list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration(mock_ctx):
    """Tests that get_transaction_info returns full data and omits raw_input by default."""
    # This is a stable transaction with a known decoded input (a swap).
    tx_hash = "0xd4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    result = await get_transaction_info(chain_id="1", hash=tx_hash, ctx=mock_ctx)

    # Assert that the main data is present and transformed
    assert isinstance(result, dict)
    assert "hash" not in result
    assert result["status"] == "ok"
    assert "decoded_input" in result and result["decoded_input"] is not None
    assert "raw_input" not in result
    assert isinstance(result.get("from"), str)
    assert result["from"].startswith("0x")
    assert isinstance(result.get("to"), str)
    assert result["to"].startswith("0x")

    # Assert token_transfers optimized
    assert "token_transfers" in result and isinstance(result["token_transfers"], list)
    for transfer in result["token_transfers"]:
        assert "block_hash" not in transfer
        assert "block_number" not in transfer
        assert "transaction_hash" not in transfer
        assert "timestamp" not in transfer
        assert isinstance(transfer.get("from"), str)
        assert isinstance(transfer.get("to"), str)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration_no_decoded_input(mock_ctx):
    """Tests that get_transaction_info keeps raw_input by default when decoded_input is null."""
    # This is a stable contract creation transaction, which has no decoded_input.
    tx_hash = "0x12341be874149efc8c714f4ef431db0ce29f64532e5c70d3882257705e2b1ad2"
    result = await get_transaction_info(chain_id="1", hash=tx_hash, ctx=mock_ctx)

    # Assert that the main data is present and transformed
    assert isinstance(result, dict)
    assert "hash" not in result
    assert result["decoded_input"] is None
    assert isinstance(result.get("from"), str)
    assert result.get("to") is None

    # raw_input should still be present
    assert "raw_input" in result
    assert isinstance(result["raw_input"], str) and len(result["raw_input"]) > 2

    assert "token_transfers" in result and len(result["token_transfers"]) > 0
    first_transfer = result["token_transfers"][0]
    assert isinstance(first_transfer.get("from"), str)
    assert isinstance(first_transfer.get("to"), str)
    assert first_transfer.get("type") == "token_minting"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transactions_by_address_integration(mock_ctx):
    """Tests that get_transactions_by_address returns a transformed list of transactions."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    result = await get_transactions_by_address(
        chain_id="1",
        address=address,
        age_to="2016-01-01T00:00:00.00Z",
        ctx=mock_ctx,
    )

    assert isinstance(result, dict)
    assert "items" in result
    items = result["items"]
    assert isinstance(items, list)

    if not items:
        pytest.skip("No transactions found for the given address and time range.")

    for item in items:
        assert isinstance(item.get("from"), str)
        assert isinstance(item.get("to"), str)
        assert "token" not in item
        assert "total" not in item


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_token_transfers_by_address_integration(mock_ctx):
    """Tests that get_token_transfers_by_address returns a transformed list of transfers."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    result = await get_token_transfers_by_address(
        chain_id="1",
        address=address,
        age_to="2017-01-01T00:00:00.00Z",
        ctx=mock_ctx,
    )

    assert isinstance(result, dict)
    assert "items" in result
    items = result["items"]
    assert isinstance(items, list)

    if not items:
        pytest.skip("No token transfers found for the given address and time range.")

    for item in items:
        assert isinstance(item.get("from"), str)
        assert isinstance(item.get("to"), str)
        assert "value" not in item
        assert "internal_transaction_index" not in item
