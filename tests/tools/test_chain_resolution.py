# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import anyio
import httpx
import pytest

from blockscout_mcp_server.cache import ChainCache, ProApiConfigCache
from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools import common
from blockscout_mcp_server.tools.common import ChainNotFoundError

pytestmark = pytest.mark.anyio


class MockAsyncClient:
    def __init__(self, response: httpx.Response | None = None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str, **kwargs) -> httpx.Response:
        if self._exc:
            raise self._exc
        return self._response


@pytest.fixture(autouse=True)
def reset_caches(monkeypatch):
    monkeypatch.setattr(common, "pro_api_config_cache", ProApiConfigCache())
    monkeypatch.setattr(common, "chain_cache", ChainCache())


async def test_fetch_pro_api_config_normalizes_urls_and_accepts_empty():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(
        200, json={"chains": {"1": "https://eth/", "137": "https://polygon", "x": ""}}, request=request
    )
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        result = await common._fetch_pro_api_config()
    assert result == {"1": "https://eth", "137": "https://polygon"}


async def test_fetch_pro_api_config_invalid_payload_and_json_error():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    invalid = httpx.Response(200, json={"endpoint_pricing": {}}, request=request)
    bad_json = httpx.Response(200, text="not-json", request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(invalid)):
        with pytest.raises(ValueError):
            await common._fetch_pro_api_config()
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(bad_json)):
        with pytest.raises(ValueError):
            await common._fetch_pro_api_config()


async def test_fetch_pro_api_config_http_error():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(500, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        with pytest.raises(httpx.HTTPStatusError):
            await common._fetch_pro_api_config()


async def test_ensure_pro_api_config_cache_and_failures(monkeypatch):
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 1)
    with (
        patch(
            "blockscout_mcp_server.tools.common._fetch_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch.object(common.pro_api_config_cache, "store_snapshot") as store,
        patch.object(common.chain_cache, "bulk_set", new_callable=AsyncMock) as bulk,
    ):
        out = await common.ensure_pro_api_config()
        assert out["1"] == "https://eth"
        store.assert_called_once()
        bulk.assert_awaited_once()

    with (
        patch(
            "blockscout_mcp_server.tools.common._fetch_pro_api_config",
            new_callable=AsyncMock,
            side_effect=ValueError("bad"),
        ),
        patch.object(common.pro_api_config_cache, "store_snapshot") as store,
        patch.object(common.chain_cache, "bulk_set", new_callable=AsyncMock) as bulk,
    ):
        with pytest.raises(ValueError):
            await common.ensure_pro_api_config()
        store.assert_not_called()
        bulk.assert_not_awaited()


async def test_ensure_pro_api_config_refresh_after_ttl(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 1)
    seq = [{"1": "https://eth"}, {"1": "https://eth2"}]
    with patch("blockscout_mcp_server.tools.common._fetch_pro_api_config", new_callable=AsyncMock, side_effect=seq):
        assert (await common.ensure_pro_api_config())["1"] == "https://eth"
        t = 2.0
        assert (await common.ensure_pro_api_config())["1"] == "https://eth2"


async def test_ensure_pro_api_config_concurrent_dedup():
    common.pro_api_config_cache = ProApiConfigCache()
    calls = 0

    async def _fetch():
        nonlocal calls
        calls += 1
        await anyio.sleep(0.01)
        return {"1": "https://eth"}

    with patch("blockscout_mcp_server.tools.common._fetch_pro_api_config", side_effect=_fetch):
        async with anyio.create_task_group() as tg:
            tg.start_soon(common.ensure_pro_api_config)
            tg.start_soon(common.ensure_pro_api_config)
    assert calls == 1


async def test_get_blockscout_base_url_paths():
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config", AsyncMock(return_value={"1": "https://eth"})
    ) as ensure:
        assert await common.get_blockscout_base_url("1") == "https://eth"
        ensure.assert_awaited_once()

    await common.chain_cache.set("1", "https://cached")
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config", AsyncMock(return_value={"1": "https://eth"})
    ) as ensure:
        assert await common.get_blockscout_base_url("1") == "https://cached"
        ensure.assert_not_awaited()

    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config", AsyncMock(return_value={"480": "https://world"})
    ):
        with pytest.raises(ChainNotFoundError):
            await common.get_blockscout_base_url("17000")


async def test_fetch_pro_api_config_rejects_non_dict_chains():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(200, json={"chains": "not-a-dict"}, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        with pytest.raises(ValueError):
            await common._fetch_pro_api_config()


async def test_fetch_pro_api_config_accepts_empty_chains_dict():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(200, json={"chains": {}}, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        result = await common._fetch_pro_api_config()
    assert result == {}
