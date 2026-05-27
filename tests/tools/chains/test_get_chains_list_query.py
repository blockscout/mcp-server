# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.models import ChainInfo
from blockscout_mcp_server.tools.chains.get_chains_list import get_chains_list
from blockscout_mcp_server.tools.common import ChainsListCache


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    cache = ChainsListCache()
    monkeypatch.setattr("blockscout_mcp_server.tools.chains.get_chains_list.chains_list_cache", cache)
    return cache


@pytest.mark.asyncio
async def test_get_chains_list_query_filters(reset_cache, mock_ctx):
    chains = [
        ChainInfo(name="Ethereum", chain_id="1", is_testnet=False, native_currency="ETH", ecosystem="Ethereum"),
        ChainInfo(
            name="OP Mainnet",
            chain_id="10",
            is_testnet=False,
            native_currency="ETH",
            ecosystem=["Optimism", "Superchain"],
        ),
        ChainInfo(name="Gnosis", chain_id="100", is_testnet=False, native_currency="XDAI", ecosystem="Gnosis"),
    ]
    reset_cache.store_snapshot(chains)
    assert len((await get_chains_list(ctx=mock_ctx, query="ethereum")).data) == 1
    assert len((await get_chains_list(ctx=mock_ctx, query="10")).data) == 2
    assert len((await get_chains_list(ctx=mock_ctx, query="xdai")).data) == 1
    assert len((await get_chains_list(ctx=mock_ctx, query="superchain")).data) == 1


@pytest.mark.asyncio
async def test_get_chains_list_query_empty_and_no_match(reset_cache, mock_ctx):
    chains = [
        ChainInfo(name="Polygon PoS", chain_id="137", is_testnet=False, native_currency="POL", ecosystem="Polygon")
    ]
    reset_cache.store_snapshot(chains)
    assert len((await get_chains_list(ctx=mock_ctx, query="")).data) == 1
    assert len((await get_chains_list(ctx=mock_ctx, query="   ")).data) == 1
    res = await get_chains_list(ctx=mock_ctx, query="nothing")
    assert res.data == []
    assert res.notes and "No chains matched query" in res.notes[0]


@pytest.mark.asyncio
async def test_get_chains_list_query_cold_cache_does_not_corrupt_cache(mock_ctx):
    mock_response = {
        "1": {
            "name": "Ethereum",
            "isTestnet": False,
            "native_currency": "ETH",
            "ecosystem": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        },
        "137": {
            "name": "Polygon PoS",
            "isTestnet": False,
            "native_currency": "POL",
            "ecosystem": "Polygon",
            "explorers": [{"hostedBy": "blockscout", "url": "https://polygon"}],
        },
    }
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth", "137": "https://polygon"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
        ) as mock_req,
    ):
        mock_req.return_value = mock_response
        filtered = await get_chains_list(ctx=mock_ctx, query="polygon")
        full = await get_chains_list(ctx=mock_ctx)
    assert len(filtered.data) == 1
    assert len(full.data) == 2
    mock_req.assert_called_once()
