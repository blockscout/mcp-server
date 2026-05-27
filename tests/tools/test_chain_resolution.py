# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import anyio
import httpx
import pytest

from blockscout_mcp_server.cache import ChainCache, ProApiConfigCache
from blockscout_mcp_server.tools import common
from blockscout_mcp_server.tools.common import ChainNotFoundError

pytestmark = pytest.mark.anyio


class MockAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return self._response


@pytest.fixture(autouse=True)
def reset_caches(monkeypatch):
    monkeypatch.setattr(common, "pro_api_config_cache", ProApiConfigCache())
    monkeypatch.setattr(common, "chain_cache", ChainCache())


async def test_fetch_pro_api_config_success():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(200, json={"chains": {"1": "https://eth.blockscout.com/"}}, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        result = await common._fetch_pro_api_config()
    assert result == {"1": "https://eth.blockscout.com"}


async def test_fetch_pro_api_config_invalid_payload():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(200, json={"endpoint_pricing": {}}, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        with pytest.raises(ValueError, match="missing or invalid 'chains' key"):
            await common._fetch_pro_api_config()


async def test_fetch_pro_api_config_http_error():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(500, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        with pytest.raises(httpx.HTTPStatusError):
            await common._fetch_pro_api_config()


async def test_ensure_pro_api_config_cache_hit():
    common.pro_api_config_cache.store_snapshot({"1": "https://eth"})
    with patch("blockscout_mcp_server.tools.common._fetch_pro_api_config", new_callable=AsyncMock) as fetch:
        result = await common.ensure_pro_api_config()
    fetch.assert_not_awaited()
    assert result == {"1": "https://eth"}


async def test_ensure_pro_api_config_concurrent_dedup():
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


async def test_get_blockscout_base_url_unsupported_chain():
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config", AsyncMock(return_value={"1": "https://eth"})
    ):
        with pytest.raises(ChainNotFoundError):
            await common.get_blockscout_base_url("999999")
