import pytest

from blockscout_mcp_server.tools.block_tools import get_latest_block
from tests.conftest import mock_ctx


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_block_integration(mock_ctx):
    result = await get_latest_block(chain_id="1", ctx=mock_ctx)

    assert isinstance(result, dict)
    assert "block_number" in result and isinstance(result["block_number"], int)
    assert "timestamp" in result and isinstance(result["timestamp"], str)
