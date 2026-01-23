import pytest

from blockscout_mcp_server.tools.block.get_block_number import get_block_number
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_number_latest_real(mock_ctx):
    """Test that get_block_number returns a latest block number and timestamp."""
    result = await retry_on_network_error(
        lambda: get_block_number(chain_id="1", ctx=mock_ctx),
        action_description="get_block_number latest request",
    )
    assert isinstance(result.data.block_number, int)
    assert result.data.block_number > 0
    assert isinstance(result.data.timestamp, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_number_by_time_real(mock_ctx):
    """Test that get_block_number resolves a block by datetime."""
    result = await retry_on_network_error(
        lambda: get_block_number(chain_id="1", ctx=mock_ctx, datetime="2023-01-01T00:00:00Z"),
        action_description="get_block_number by datetime request",
    )
    assert isinstance(result.data.block_number, int)
    assert result.data.block_number > 0
    assert isinstance(result.data.timestamp, str)
