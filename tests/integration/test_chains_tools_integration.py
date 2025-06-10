import pytest

from blockscout_mcp_server.tools.chains_tools import get_chains_list
from tests.conftest import mock_ctx


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chains_list_integration(mock_ctx):
    """Tests that get_chains_list returns a formatted string and contains known, stable chains."""
    result = await get_chains_list(ctx=mock_ctx)

    # Assert that the result is a string and not empty
    assert isinstance(result, str)
    assert len(result) > 0

    # Assert that the output contains a well-known, stable chain entry.
    # This verifies that the name and chainid fields were correctly extracted and formatted.
    assert "Ethereum: 1" in result
    assert "Polygon PoS: 137" in result
