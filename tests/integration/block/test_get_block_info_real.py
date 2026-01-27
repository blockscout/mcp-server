import pytest

from blockscout_mcp_server.tools.block.get_block_info import get_block_info
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_info_integration(mock_ctx):
    """Test get_block_info for a stable, historical block without transactions."""
    block_number = "19000000"
    result = await retry_on_network_error(
        lambda: get_block_info(chain_id="1", number_or_hash=block_number, ctx=mock_ctx),
        action_description="get_block_info request",
    )

    assert hasattr(result, "data")
    assert hasattr(result.data, "block_details")
    assert result.data.block_details["height"] == 19000000
    assert "hash" in result.data.block_details
    assert result.data.transaction_hashes is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_info_with_transactions_integration(mock_ctx):
    """Test get_block_info with include_transactions=True and verify live transaction counts."""
    block_number = "1000000"
    result = await retry_on_network_error(
        lambda: get_block_info(
            chain_id="1",
            number_or_hash=block_number,
            include_transactions=True,
            ctx=mock_ctx,
        ),
        action_description="get_block_info request",
    )

    assert hasattr(result, "data")
    details = result.data.block_details
    hashes = result.data.transaction_hashes

    assert details["height"] == 1000000
    assert isinstance(hashes, list)
    assert details["transactions_count"] == len(hashes)
    assert details["transactions_count"] > 0
    assert all(tx.startswith("0x") for tx in hashes)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_info_with_no_transactions_integration(mock_ctx):
    """Test get_block_info with include_transactions=True for a block with zero transactions."""
    block_number = "100"
    result = await retry_on_network_error(
        lambda: get_block_info(
            chain_id="1",
            number_or_hash=block_number,
            include_transactions=True,
            ctx=mock_ctx,
        ),
        action_description="get_block_info request",
    )

    assert hasattr(result, "data")
    details = result.data.block_details
    hashes = result.data.transaction_hashes

    assert details["height"] == 100
    assert details["transactions_count"] == 0
    assert isinstance(hashes, list)
    assert len(hashes) == 0
