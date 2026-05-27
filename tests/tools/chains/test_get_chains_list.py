# SPDX-License-Identifier: LicenseRef-Blockscout
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import blockscout_mcp_server.tools.common as common_tools
from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ChainInfo, ToolResponse
from blockscout_mcp_server.tools.chains.get_chains_list import get_chains_list
from blockscout_mcp_server.tools.common import ChainsListCache


@pytest.fixture(autouse=True)
def reset_chains_list_cache(monkeypatch):
    new_cache = ChainsListCache()
    monkeypatch.setattr(common_tools, "chains_list_cache", new_cache)
    monkeypatch.setattr("blockscout_mcp_server.tools.chains.get_chains_list.chains_list_cache", new_cache)


@pytest.mark.asyncio
async def test_get_chains_list_success(mock_ctx):
    mock_api_response = {
        "1": {"name": "Ethereum", "isTestnet": False, "native_currency": "ETH", "ecosystem": "Ethereum"},
        "137": {
            "name": "Polygon PoS",
            "isTestnet": False,
            "native_currency": "POL",
            "ecosystem": "Polygon",
            "settlementLayerChainId": "1",
        },
    }
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config", new_callable=AsyncMock
        ) as mock_pro,
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_pro.return_value = {"1": "https://eth", "137": "https://polygon"}
        mock_request.return_value = mock_api_response
        result = await get_chains_list(ctx=mock_ctx)
    assert isinstance(result, ToolResponse)
    assert [c.chain_id for c in result.data] == ["1", "137"]
    assert result.content_text == "Retrieved 2 supported blockchain chains."


@pytest.mark.asyncio
async def test_get_chains_list_refresh_error(mock_ctx, monkeypatch):
    fake_now = 0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: fake_now)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)
    api_error = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503))
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[{"1": {"name": "Ethereum"}}, api_error],
        ) as mock_request,
    ):
        await get_chains_list(ctx=mock_ctx)
        fake_now += 3
        with pytest.raises(httpx.HTTPStatusError):
            await get_chains_list(ctx=mock_ctx)
    assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_true_concurrent_calls(mock_ctx, monkeypatch):
    fake_now = 0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: fake_now)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)
    call_count = 0
    first_call_started = asyncio.Event()
    first_call_can_complete = asyncio.Event()

    async def controlled_mock_request(*, api_path: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_call_started.set()
            await first_call_can_complete.wait()
        return {"1": {"name": "Ethereum"}}

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=controlled_mock_request,
        ),
    ):
        t1 = asyncio.create_task(get_chains_list(ctx=mock_ctx))
        t2 = asyncio.create_task(get_chains_list(ctx=mock_ctx))
        await first_call_started.wait()
        first_call_can_complete.set()
        r1, r2 = await asyncio.gather(t1, t2)
    assert call_count == 1
    assert r1.data == r2.data


@pytest.mark.asyncio
async def test_get_chains_list_cached_progress_reporting(mock_ctx):
    common_tools.chains_list_cache.store_snapshot(
        [ChainInfo(name="Ethereum", chain_id="1", is_testnet=False, native_currency="ETH", ecosystem="Ethereum")]
    )
    with patch(
        "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        result = await get_chains_list(ctx=mock_ctx)
    mock_request.assert_not_called()
    assert result.data[0].name == "Ethereum"
