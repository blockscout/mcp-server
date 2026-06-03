# SPDX-License-Identifier: LicenseRef-Blockscout
import json
from unittest.mock import AsyncMock, patch

import anyio
import httpx
import pytest

from blockscout_mcp_server.cache import ProApiConfigCache
from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools import common

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


async def test_fetch_pro_api_config_normalizes_urls_and_accepts_empty():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(
        200, json={"chains": {"1": "https://eth/", "137": "https://polygon", "x": ""}}, request=request
    )
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        result = await common._fetch_pro_api_config()
    assert result == {"1": "https://eth", "137": "https://polygon"}


async def test_fetch_pro_api_config_missing_chains_key():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    invalid = httpx.Response(200, json={"endpoint_pricing": {}}, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(invalid)):
        with pytest.raises(ValueError, match="missing or invalid 'chains' key"):
            await common._fetch_pro_api_config()


async def test_fetch_pro_api_config_malformed_json():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    bad_json = httpx.Response(200, text="not-json", request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(bad_json)):
        with pytest.raises(json.JSONDecodeError):
            await common._fetch_pro_api_config()


async def test_fetch_pro_api_config_http_error():
    request = httpx.Request("GET", "https://api.blockscout.com/api/json/config")
    response = httpx.Response(500, request=request)
    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=MockAsyncClient(response)):
        with pytest.raises(httpx.HTTPStatusError):
            await common._fetch_pro_api_config()


async def test_ensure_pro_api_config_cache_and_failures(monkeypatch):
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    with (
        patch(
            "blockscout_mcp_server.tools.common._fetch_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch.object(common.pro_api_config_cache, "store_snapshot") as store,
    ):
        out = await common.ensure_pro_api_config()
        assert out["1"] == "https://eth"
        store.assert_called_once()

    with (
        patch(
            "blockscout_mcp_server.tools.common._fetch_pro_api_config",
            new_callable=AsyncMock,
            side_effect=ValueError("bad"),
        ),
        patch.object(common.pro_api_config_cache, "store_snapshot") as store,
    ):
        with pytest.raises(ValueError):
            await common.ensure_pro_api_config()
        store.assert_not_called()


async def test_ensure_pro_api_config_refresh_after_ttl(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
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


async def test_ensure_pro_api_config_stale_on_error(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        return_value={"1": "https://eth"},
    ):
        assert (await common.ensure_pro_api_config())["1"] == "https://eth"
    t = 2.0
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError(
            "x",
            request=httpx.Request("GET", "https://x"),
            response=httpx.Response(503, request=httpx.Request("GET", "https://x")),
        ),
    ):
        assert (await common.ensure_pro_api_config())["1"] == "https://eth"


async def test_ensure_pro_api_config_no_stale_raises():
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError(
            "x",
            request=httpx.Request("GET", "https://x"),
            response=httpx.Response(503, request=httpx.Request("GET", "https://x")),
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await common.ensure_pro_api_config()


async def test_ensure_pro_api_config_stale_logs_warning(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        return_value={"1": "https://eth"},
    ):
        await common.ensure_pro_api_config()
    t = 2.0
    with (
        patch(
            "blockscout_mcp_server.tools.common._fetch_pro_api_config",
            new_callable=AsyncMock,
            side_effect=ValueError("bad"),
        ),
        patch("blockscout_mcp_server.tools.common.logger.warning") as warn,
    ):
        await common.ensure_pro_api_config()
    warn.assert_called_once()


async def test_ensure_pro_api_config_stale_failure_uses_cooldown(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    monkeypatch.setattr(config, "pro_api_config_refresh_retry_seconds", 30)
    fetch = AsyncMock(
        side_effect=[
            {"1": "https://eth"},
            httpx.HTTPStatusError(
                "x",
                request=httpx.Request("GET", "https://x"),
                response=httpx.Response(503, request=httpx.Request("GET", "https://x")),
            ),
        ]
    )
    with patch("blockscout_mcp_server.tools.common._fetch_pro_api_config", fetch):
        assert (await common.ensure_pro_api_config())["1"] == "https://eth"
        t = 2.0
        assert (await common.ensure_pro_api_config())["1"] == "https://eth"
        assert (await common.ensure_pro_api_config())["1"] == "https://eth"
    assert fetch.await_count == 2


async def test_ensure_pro_api_config_retries_after_cooldown(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    monkeypatch.setattr(config, "pro_api_config_refresh_retry_seconds", 5)
    fetch = AsyncMock(
        side_effect=[
            {"1": "https://eth"},
            httpx.HTTPStatusError(
                "x",
                request=httpx.Request("GET", "https://x"),
                response=httpx.Response(503, request=httpx.Request("GET", "https://x")),
            ),
            {"1": "https://eth2"},
        ]
    )
    with patch("blockscout_mcp_server.tools.common._fetch_pro_api_config", fetch):
        await common.ensure_pro_api_config()
        t = 2.0
        await common.ensure_pro_api_config()
        t = 8.0
        assert (await common.ensure_pro_api_config())["1"] == "https://eth2"
    assert fetch.await_count == 3


async def test_ensure_pro_api_config_success_invalidates_chains_list_cache():
    common.chains_list_cache.store_snapshot([])
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        return_value={"1": "https://eth"},
    ):
        await common.ensure_pro_api_config()
    assert common.chains_list_cache.get_if_fresh() is None


async def test_ensure_pro_api_config_stale_fallback_does_not_invalidate_chains_list_cache(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    common.chains_list_cache.store_snapshot([])
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        return_value={"1": "https://eth"},
    ):
        await common.ensure_pro_api_config()
    common.chains_list_cache.store_snapshot([])
    t = 2.0
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        side_effect=ValueError("bad"),
    ):
        await common.ensure_pro_api_config()
    assert common.chains_list_cache.get_if_fresh() == []


async def test_ensure_pro_api_config_does_not_swallow_programming_errors(monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "pro_api_config_ttl_seconds", 1)
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        return_value={"1": "https://eth"},
    ):
        await common.ensure_pro_api_config()

    t = 2.0
    with patch(
        "blockscout_mcp_server.tools.common._fetch_pro_api_config",
        new_callable=AsyncMock,
        side_effect=AttributeError("bug in code"),
    ):
        with pytest.raises(AttributeError):
            await common.ensure_pro_api_config()


async def test_fetch_pro_api_config_does_not_send_pro_api_key(monkeypatch):
    """PRO API key must never appear in _fetch_pro_api_config outgoing requests.

    Security regression for issue #375: the keyless config endpoint must stay
    keyless even when a PRO API key is configured.  This test patches
    httpx.AsyncClient at the class level (NOT _create_httpx_client) so that
    any default-header or auth leak introduced inside _create_httpx_client is
    also caught.
    """
    from blockscout_mcp_server.config import config as cfg

    monkeypatch.setattr(cfg, "pro_api_key", "proapi_test")

    # Build a stub response for the config endpoint
    request = httpx.Request("GET", cfg.pro_api_config_url)
    stub_response = httpx.Response(200, json={"chains": {"1": "https://eth"}}, request=request)

    captured_constructor_kwargs: dict = {}
    captured_get_kwargs: dict = {}

    class CapturingClientClass:
        """Mimics httpx.AsyncClient at the class level."""

        def __init__(self, **kwargs):
            captured_constructor_kwargs.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str, **kwargs) -> httpx.Response:
            captured_get_kwargs.update(kwargs)
            return stub_response

    with patch("blockscout_mcp_server.tools.common.httpx.AsyncClient", CapturingClientClass):
        result = await common._fetch_pro_api_config()

    assert result == {"1": "https://eth"}

    # Constructor must not carry auth material
    assert "Authorization" not in (captured_constructor_kwargs.get("headers") or {})
    assert "auth" not in captured_constructor_kwargs

    # Per-request .get() kwargs must also be clean
    assert "Authorization" not in (captured_get_kwargs.get("headers") or {})
    assert "auth" not in captured_get_kwargs
