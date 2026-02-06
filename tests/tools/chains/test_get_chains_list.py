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
    """Verify that get_chains_list correctly processes a successful API response."""
    mock_api_response = {
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
            "settlementLayerChainId": "1",
            "explorers": [{"hostedBy": "blockscout", "url": "https://polygon"}],
        },
    }

    expected_data = [
        ChainInfo(
            name="Ethereum",
            chain_id="1",
            is_testnet=False,
            native_currency="ETH",
            ecosystem="Ethereum",
            settlement_layer_chain_id=None,
        ),
        ChainInfo(
            name="Polygon PoS",
            chain_id="137",
            is_testnet=False,
            native_currency="POL",
            ecosystem="Polygon",
            settlement_layer_chain_id="1",
        ),
    ]

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains.get_chains_list.chain_cache") as mock_chain_cache,
    ):
        mock_request.return_value = mock_api_response
        mock_chain_cache.bulk_set = AsyncMock()

        result = await get_chains_list(ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path="/api/chains")
        expected_cache_payload = {"1": "https://eth", "137": "https://polygon"}
        mock_chain_cache.bulk_set.assert_awaited_once_with(expected_cache_payload)
        assert isinstance(result, ToolResponse)
        assert [chain.model_dump() for chain in result.data] == [chain.model_dump() for chain in expected_data]
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        assert result.content_text == "Retrieved 2 known blockchain chains."


@pytest.mark.asyncio
async def test_get_chains_list_caches_filtered_chains(mock_ctx):
    """Verify that get_chains_list caches only chains with Blockscout explorers."""
    mock_api_response = {
        "1": {"name": "Ethereum", "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}]},
        "999": {"name": "No Blockscout", "explorers": [{"hostedBy": "other", "url": "https://other"}]},
    }

    with patch(
        "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        with patch("blockscout_mcp_server.tools.chains.get_chains_list.chain_cache") as mock_cache:
            mock_request.return_value = mock_api_response
            mock_cache.bulk_set = AsyncMock()

            result = await get_chains_list(ctx=mock_ctx)

            mock_cache.bulk_set.assert_awaited_once()
            cached = mock_cache.bulk_set.call_args.args[0]
            assert cached == {"1": "https://eth"}
            assert isinstance(result, ToolResponse)
            assert [chain.chain_id for chain in result.data] == ["1"]


@pytest.mark.asyncio
async def test_get_chains_list_empty_response(mock_ctx):
    """Verify that get_chains_list handles empty API responses gracefully."""
    mock_api_response: dict[str, dict] = {}
    expected_data: list[ChainInfo] = []

    with patch(
        "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        result = await get_chains_list(ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path="/api/chains")
        assert isinstance(result, ToolResponse)
        assert result.data == expected_data
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_invalid_response_format(mock_ctx):
    """Verify that get_chains_list handles invalid response formats gracefully."""
    mock_api_response = {"error": "Invalid data"}
    expected_data: list[ChainInfo] = []

    with patch(
        "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        result = await get_chains_list(ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path="/api/chains")
        assert isinstance(result, ToolResponse)
        assert result.data == expected_data
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_chains_with_missing_fields(mock_ctx):
    """Verify that get_chains_list handles chains with missing name or chain ID fields."""
    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "isTestnet": False,
            "native_currency": "ETH",
            "ecosystem": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        },
        "invalid": {"name": "Incomplete Chain"},
        "137": {
            "name": "Polygon PoS",
            "isTestnet": False,
            "native_currency": "POL",
            "ecosystem": "Polygon",
            "explorers": [{"hostedBy": "blockscout", "url": "https://polygon"}],
        },
        "empty": {},
    }

    expected_data = [
        ChainInfo(
            name="Ethereum",
            chain_id="1",
            is_testnet=False,
            native_currency="ETH",
            ecosystem="Ethereum",
            settlement_layer_chain_id=None,
        ),
        ChainInfo(
            name="Polygon PoS",
            chain_id="137",
            is_testnet=False,
            native_currency="POL",
            ecosystem="Polygon",
            settlement_layer_chain_id=None,
        ),
    ]

    with patch(
        "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        result = await get_chains_list(ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path="/api/chains")
        assert isinstance(result, ToolResponse)
        assert result.data == expected_data
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2


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
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains.get_chains_list.chain_cache") as mock_chain_cache,
    ):
        mock_request.return_value = mock_api_response
        mock_chain_cache.bulk_set = AsyncMock()

        result1 = await get_chains_list(ctx=mock_ctx)
        fake_now += 1
        result2 = await get_chains_list(ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path="/api/chains")
        mock_chain_cache.bulk_set.assert_awaited_once()
        assert result1.data == result2.data
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


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
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[mock_api_response_1, mock_api_response_2],
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains.get_chains_list.chain_cache") as mock_chain_cache,
    ):
        mock_chain_cache.bulk_set = AsyncMock()

        result1 = await get_chains_list(ctx=mock_ctx)
        fake_now += 3
        result2 = await get_chains_list(ctx=mock_ctx)

        assert mock_request.call_count == 2
        assert mock_chain_cache.bulk_set.await_count == 2
        assert result1.data != result2.data
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


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
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[mock_api_response, api_error],
        ) as mock_request,
        patch("blockscout_mcp_server.tools.chains.get_chains_list.chain_cache") as mock_chain_cache,
    ):
        mock_chain_cache.bulk_set = AsyncMock()

        await get_chains_list(ctx=mock_ctx)
        fake_now += 3
        with pytest.raises(httpx.HTTPStatusError):
            await get_chains_list(ctx=mock_ctx)

        assert mock_request.call_count == 2
        assert mock_chain_cache.bulk_set.await_count == 1
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_chains_list_sequential_calls_use_cache(mock_ctx, monkeypatch):
    """Sequential calls within TTL are served from cache (single upstream call)."""
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

    call_count = 0

    async def mock_request(*, api_path: str):
        nonlocal call_count
        call_count += 1
        return mock_api_response

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=mock_request,
        ) as mock_api_request,
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.chain_cache.bulk_set",
            new_callable=AsyncMock,
        ) as mock_bulk_set,
    ):
        result1 = await get_chains_list(ctx=mock_ctx)
        result2 = await get_chains_list(ctx=mock_ctx)

        assert call_count == 1
        assert mock_api_request.call_count == 1
        assert mock_bulk_set.call_count == 1
        assert result1.data == result2.data
        assert len(result1.data) == 1
        assert result1.data[0].name == "Ethereum"
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


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

    call_count = 0
    first_call_started = asyncio.Event()
    first_call_can_complete = asyncio.Event()

    async def controlled_mock_request(*, api_path: str):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            first_call_started.set()
            await first_call_can_complete.wait()

        return mock_api_response

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=controlled_mock_request,
        ) as mock_api_request,
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.chain_cache.bulk_set",
            new_callable=AsyncMock,
        ) as mock_bulk_set,
    ):

        async def run_concurrent_test():
            task1 = asyncio.create_task(get_chains_list(ctx=mock_ctx))
            task2 = asyncio.create_task(get_chains_list(ctx=mock_ctx))

            await first_call_started.wait()
            first_call_can_complete.set()

            results = await asyncio.gather(task1, task2)
            return results

        results = await run_concurrent_test()

        assert call_count == 1
        assert mock_api_request.call_count == 1
        assert mock_bulk_set.call_count == 1
        assert len(results) == 2
        assert results[0].data == results[1].data
        assert len(results[0].data) == 1
        assert results[0].data[0].name == "Ethereum"
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_chains_list_cached_progress_reporting(mock_ctx):
    common_tools.chains_list_cache.store_snapshot(
        [
            ChainInfo(
                name="Ethereum",
                chain_id="1",
                is_testnet=False,
                native_currency="ETH",
                ecosystem="Ethereum",
            )
        ]
    )

    with patch(
        "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        result = await get_chains_list(ctx=mock_ctx)

    mock_request.assert_not_called()
    assert mock_ctx.report_progress.await_count == 2
    assert mock_ctx.info.await_count == 2
    assert result.data[0].name == "Ethereum"
