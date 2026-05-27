# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

import blockscout_mcp_server.tools.common as common_tools
from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.chains.get_chains_list import get_chains_list
from blockscout_mcp_server.tools.common import ChainsListCache


@pytest.fixture(autouse=True)
def reset_chains_list_cache(monkeypatch):
    new_cache = ChainsListCache()
    monkeypatch.setattr(common_tools, "chains_list_cache", new_cache)
    monkeypatch.setattr("blockscout_mcp_server.tools.chains.get_chains_list.chains_list_cache", new_cache)


@pytest.mark.asyncio
async def test_get_chains_list_join_and_filters(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth", "3946": "https://x"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}, "17000": {"name": "Holesky"}},
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx)
    assert [c.chain_id for c in res.data] == ["1"]


@pytest.mark.asyncio
async def test_get_chains_list_empty_pro_config(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}},
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx)
    assert res.data == []


@pytest.mark.asyncio
async def test_get_chains_list_cache_hit_and_refresh(mock_ctx, monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 1)
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            side_effect=[{"1": "https://eth"}, {"137": "https://polygon"}],
        ) as pro,
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[{"1": {"name": "Ethereum"}}, {"137": {"name": "Polygon"}}],
        ) as cs,
    ):
        first = await get_chains_list(ctx=mock_ctx)
        second = await get_chains_list(ctx=mock_ctx)
        assert first.data == second.data
        assert pro.await_count == 1
        assert cs.await_count == 1
        t = 2.0
        third = await get_chains_list(ctx=mock_ctx)
        assert [c.chain_id for c in third.data] == ["137"]
        assert pro.await_count == 2
        assert cs.await_count == 2
