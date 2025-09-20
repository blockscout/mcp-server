import pytest

from blockscout_mcp_server.tools.block.get_latest_block import get_latest_block


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_block_integration(mock_ctx):
    result = await get_latest_block(chain_id="1", ctx=mock_ctx)

    assert hasattr(result, "data")
    assert hasattr(result.data, "block_number")
    assert hasattr(result.data, "timestamp")
    assert isinstance(result.data.block_number, int)
    assert isinstance(result.data.timestamp, str)
    assert result.data.block_number > 0
