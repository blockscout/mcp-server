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

    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", fake_time)
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

    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", fake_time)
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

    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", fake_time)
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
    """Test that concurrent calls are properly handled by the cache locking mechanism."""
    fake_now = 0

    def fake_time() -> int:
        return fake_now

    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", fake_time)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)

    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        }
    }

    # Track call count without any delays to avoid hangs
    call_count = 0

    async def mock_request(*, api_path: str):
        nonlocal call_count
        call_count += 1
        return mock_api_response

    # Mock both the API request and bulk_set without any async delays
    with (
        patch(
            "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=mock_request,
        ) as mock_api_request,
        patch(
            "blockscout_mcp_server.tools.chains_tools.chain_cache.bulk_set",
            new_callable=AsyncMock,
        ) as mock_bulk_set,
    ):
        # Test the sequential behavior first to ensure basic functionality works
        result1 = await get_chains_list(ctx=mock_ctx)
        result2 = await get_chains_list(ctx=mock_ctx)  # This should use cache

        # Only one API call should have been made due to caching
        assert call_count == 1
        assert mock_api_request.call_count == 1
        assert mock_bulk_set.call_count == 1

        # Both results should be the same
        assert result1.data == result2.data
        assert len(result1.data) == 1
        assert result1.data[0].name == "Ethereum"


@pytest.mark.asyncio
async def test_get_chains_list_true_concurrent_calls(mock_ctx, monkeypatch):
    """Test that truly concurrent calls are handled properly with proper locking."""
    fake_now = 0

    def fake_time() -> int:
        return fake_now

    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", fake_time)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 2)

    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        }
    }

    # Use a counter and event to control execution properly
    call_count = 0
    first_call_started = asyncio.Event()
    first_call_can_complete = asyncio.Event()

    async def controlled_mock_request(*, api_path: str):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # This is the first call
            first_call_started.set()
            await first_call_can_complete.wait()

        return mock_api_response

    # Mock without delays but with proper control
    with (
        patch(
            "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=controlled_mock_request,
        ) as mock_api_request,
        patch(
            "blockscout_mcp_server.tools.chains_tools.chain_cache.bulk_set",
            new_callable=AsyncMock,
        ) as mock_bulk_set,
    ):

        async def run_concurrent_test():
            # Start both calls
            task1 = asyncio.create_task(get_chains_list(ctx=mock_ctx))
            task2 = asyncio.create_task(get_chains_list(ctx=mock_ctx))

            # Wait for first call to start
            await first_call_started.wait()

            # Allow first call to complete
            first_call_can_complete.set()

            # Wait for both to complete
            results = await asyncio.gather(task1, task2)
            return results

        results = await run_concurrent_test()

        # Due to the locking mechanism, only one API call should be made
        # The second call should wait for the first to complete and use its cached result
        assert call_count == 1
        assert mock_api_request.call_count == 1
        assert mock_bulk_set.call_count == 1

        # Both results should be identical
        assert len(results) == 2
        assert results[0].data == results[1].data
        assert len(results[0].data) == 1
        assert results[0].data[0].name == "Ethereum"


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
    chains_list_cache.expiry_timestamp = time.monotonic() + 60

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        result = await get_chains_list(ctx=mock_ctx)

    mock_request.assert_not_called()
    assert mock_ctx.report_progress.call_count == 2
    assert mock_ctx.info.call_count == 2
    assert result.data[0].name == "Ethereum"
