import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.tools.chains_tools import get_chains_list
from blockscout_mcp_server.tools.common import chain_cache, chains_list_cache, get_blockscout_base_url


@pytest.fixture(autouse=True)
def clear_chains_list_cache():
    chains_list_cache.chains_snapshot = None
    chains_list_cache.expiry_timestamp = 0.0
    yield
    chains_list_cache.chains_snapshot = None
    chains_list_cache.expiry_timestamp = 0.0


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

    op_chain = next((chain for chain in result.data if chain.name == "OP Mainnet"), None)
    assert op_chain is not None
    assert op_chain.chain_id == "10"
    assert op_chain.is_testnet is False
    assert op_chain.native_currency == "ETH"
    assert op_chain.ecosystem == ["Optimism", "Superchain"]


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chains_list_cache_hit_skips_network(mock_ctx, monkeypatch):
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 60)
    await get_chains_list(ctx=mock_ctx)
    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        await get_chains_list(ctx=mock_ctx)
        mock_request.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chains_list_refreshes_after_ttl(mock_ctx, monkeypatch):
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 1)
    await get_chains_list(ctx=mock_ctx)
    first_expiry = chain_cache.get("1")[1]
    await asyncio.sleep(1.1)
    await get_chains_list(ctx=mock_ctx)
    second_expiry = chain_cache.get("1")[1]
    assert second_expiry > first_expiry
