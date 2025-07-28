import time

import pytest

from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.tools.chains_tools import get_chains_list
from blockscout_mcp_server.tools.common import chain_cache, get_blockscout_base_url


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
    assert eth_chain.is_testnet is False
    assert eth_chain.native_currency == "ETH"
    assert eth_chain.ecosystem == "Ethereum"

    polygon_chain = next((chain for chain in result.data if chain.name == "Polygon PoS"), None)
    assert polygon_chain is not None
    assert polygon_chain.chain_id == "137"
    assert polygon_chain.is_testnet is False
    assert polygon_chain.native_currency == "POL"
    assert polygon_chain.ecosystem == "Polygon"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chains_list_warms_cache(mock_ctx):
    """Ensure calling get_chains_list populates the chain cache."""
    await get_chains_list(ctx=mock_ctx)

    cached_entry = chain_cache.get("1")
    assert cached_entry is not None
    cached_url, expiry = cached_entry
    expected_url = await get_blockscout_base_url("1")
    assert cached_url == expected_url
    assert expiry > time.time()
