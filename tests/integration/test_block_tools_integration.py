import pytest
import json

from blockscout_mcp_server.tools.block_tools import get_latest_block, get_block_info


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_block_integration(mock_ctx):
    result = await get_latest_block(chain_id="1", ctx=mock_ctx)

    assert isinstance(result, dict)
    assert "block_number" in result and isinstance(result["block_number"], int)
    assert "timestamp" in result and isinstance(result["timestamp"], str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_info_integration(mock_ctx):
    """Test get_block_info for a stable, historical block without transactions."""
    # Using a well-known, stable block
    block_number = "19000000"
    result = await get_block_info(chain_id="1", number_or_hash=block_number, ctx=mock_ctx)

    assert isinstance(result, str)
    assert "Basic block info:" in result
    assert "Transactions in the block:" not in result

    # Parse the JSON part and check some fields
    json_part = result.replace("Basic block info:\n", "")
    data = json.loads(json_part)
    assert data["height"] == 19000000
    assert "hash" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_info_with_transactions_integration(mock_ctx):
    """Test get_block_info with include_transactions=True for a block with a known number of transactions."""
    # Block 1,000,000 on Ethereum Mainnet is stable and has exactly 7 transactions.
    block_number = "1000000"
    result = await get_block_info(chain_id="1", number_or_hash=block_number, include_transactions=True, ctx=mock_ctx)

    assert isinstance(result, str)
    assert "Basic block info:" in result
    assert "Transactions in the block:" in result

    parts = result.split("\n\n")
    assert len(parts) >= 2

    block_info_json_str = parts[0].replace("Basic block info:\n", "")
    block_info_json = json.loads(block_info_json_str)

    tx_list_json_str = parts[1].replace("Transactions in the block:\n", "")
    tx_list_json = json.loads(tx_list_json_str)

    assert block_info_json["height"] == 1000000
    assert block_info_json["transaction_count"] == 2
    assert isinstance(tx_list_json, list)
    assert len(tx_list_json) == 2
    assert all(tx.startswith("0x") for tx in tx_list_json)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_info_with_no_transactions_integration(mock_ctx):
    """Test get_block_info with include_transactions=True for a block with zero transactions."""
    # Block 100 on Ethereum Mainnet is stable and has 0 transactions.
    block_number = "100"
    result = await get_block_info(chain_id="1", number_or_hash=block_number, include_transactions=True, ctx=mock_ctx)

    assert isinstance(result, str)
    assert "Basic block info:" in result
    assert "No transactions in the block." in result
    assert "Transactions in the block:" not in result

    block_info_json_str = result.split("\n\n")[0].replace("Basic block info:\n", "")
    block_info_json = json.loads(block_info_json_str)

    assert block_info_json["height"] == 100
    assert block_info_json["transaction_count"] == 0
