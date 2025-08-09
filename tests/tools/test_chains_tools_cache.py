from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ChainInfo
from blockscout_mcp_server.tools.chains_tools import get_chains_list
from blockscout_mcp_server.tools.common import chains_list_cache


@pytest.fixture(autouse=True)
def clear_chains_list_cache():
    chains_list_cache.chains_snapshot = None
    chains_list_cache.expiry_timestamp = 0.0
    yield
    chains_list_cache.chains_snapshot = None
    chains_list_cache.expiry_timestamp = 0.0


@pytest.mark.asyncio
async def test_get_chains_list_uses_cache_within_ttl(mock_ctx, monkeypatch):
    fake_now = 0

    def fake_time() -> int:
        return fake_now

    monkeypatch.setattr("blockscout_mcp_server.cache.time.time", fake_time)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)

    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        }
    }

    with (
        patch(
            "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains_tools.chain_cache") as mock_chain_cache,
    ):
        mock_request.return_value = mock_api_response
        mock_chain_cache.bulk_set = AsyncMock()

        result1 = await get_chains_list(ctx=mock_ctx)
        fake_now += 1
        result2 = await get_chains_list(ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path="/api/chains")
        mock_chain_cache.bulk_set.assert_awaited_once()
        assert result1.data == result2.data


@pytest.mark.asyncio
async def test_get_chains_list_refreshes_after_ttl(mock_ctx, monkeypatch):
    fake_now = 0

    def fake_time() -> int:
        return fake_now

    monkeypatch.setattr("blockscout_mcp_server.cache.time.time", fake_time)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)

    mock_api_response_1 = {
        "1": {
            "name": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        }
    }
    mock_api_response_2 = {
        "137": {
            "name": "Polygon PoS",
            "explorers": [{"hostedBy": "blockscout", "url": "https://polygon"}],
        }
    }

    with (
        patch(
            "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[mock_api_response_1, mock_api_response_2],
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains_tools.chain_cache") as mock_chain_cache,
    ):
        mock_chain_cache.bulk_set = AsyncMock()

        result1 = await get_chains_list(ctx=mock_ctx)
        fake_now += 3
        result2 = await get_chains_list(ctx=mock_ctx)

        assert mock_request.call_count == 2
        assert mock_chain_cache.bulk_set.await_count == 2
        assert result1.data != result2.data


@pytest.mark.asyncio
async def test_get_chains_list_refresh_error(mock_ctx, monkeypatch):
    fake_now = 0

    def fake_time() -> int:
        return fake_now

    monkeypatch.setattr("blockscout_mcp_server.cache.time.time", fake_time)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)

    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        }
    }
    api_error = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503))

    with (
        patch(
            "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[mock_api_response, api_error],
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains_tools.chain_cache") as mock_chain_cache,
    ):
        mock_chain_cache.bulk_set = AsyncMock()

        await get_chains_list(ctx=mock_ctx)
        fake_now += 3
        with pytest.raises(httpx.HTTPStatusError):
            await get_chains_list(ctx=mock_ctx)

        assert mock_request.call_count == 2
        assert mock_chain_cache.bulk_set.await_count == 1


@pytest.mark.asyncio
async def test_get_chains_list_concurrent_calls_deduplicated(mock_ctx, monkeypatch):
    fake_now = 0

    def fake_time() -> int:
        return fake_now

    monkeypatch.setattr("blockscout_mcp_server.cache.time.time", fake_time)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)

    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        }
    }

    async def slow_request(*, api_path: str):
        await asyncio.sleep(0.1)
        return mock_api_response

    with (
        patch(
            "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=slow_request,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains_tools.chain_cache") as mock_chain_cache,
    ):
        mock_chain_cache.bulk_set = AsyncMock()

        results = await asyncio.gather(get_chains_list(ctx=mock_ctx), get_chains_list(ctx=mock_ctx))

        assert mock_request.call_count == 1
        assert mock_chain_cache.bulk_set.await_count == 1
        assert results[0].data == results[1].data


@pytest.mark.asyncio
async def test_get_chains_list_cached_progress_reporting(mock_ctx):
    chains_list_cache.chains_snapshot = [
        ChainInfo(
            name="Ethereum",
            chain_id="1",
            is_testnet=False,
            native_currency="ETH",
            ecosystem="Ethereum",
        )
    ]
    chains_list_cache.expiry_timestamp = time.time() + 60

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        result = await get_chains_list(ctx=mock_ctx)

    mock_request.assert_not_called()
    assert mock_ctx.report_progress.call_count == 2
    assert mock_ctx.info.call_count == 2
    assert result.data[0].name == "Ethereum"
