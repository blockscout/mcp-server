import pytest

from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.tools.chains_tools import get_chains_list


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chains_list_integration(mock_ctx):
    """Tests that get_chains_list returns structured data with expected chains."""
    result = await get_chains_list(ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert len(result.data) > 0

    eth_chain = next((chain for chain in result.data if chain.name == "Ethereum"), None)
    assert eth_chain is not None
    assert eth_chain.chain_id == "1"

    polygon_chain = next((chain for chain in result.data if chain.name == "Polygon PoS"), None)
    assert polygon_chain is not None
    assert polygon_chain.chain_id == "137"
