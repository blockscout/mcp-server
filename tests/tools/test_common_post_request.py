# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.common import CreditsExhaustedError, make_blockscout_post_request


class MockResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.reason_phrase = "OK"
        self.request = httpx.Request("POST", "https://api.blockscout.com/1/b")
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=self)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_make_blockscout_post_request_success_with_params_preserved():
    calls = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params, headers=None, **kwargs):
            calls.append((url, json, params.copy()))
            return MockResponse({"ok": True})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        data = await make_blockscout_post_request("1", "/b", {"x": 1}, {"q": "1"})
    assert data == {"ok": True}
    assert calls[0][2] == {"q": "1"}


@pytest.mark.asyncio
async def test_make_blockscout_post_request_retries_on_connect_error():
    attempts = {"count": 0}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *_args, **_kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ConnectError("connect failed")
            return MockResponse({"ok": True})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        result = await make_blockscout_post_request("1", "/b", {"x": 1})
    assert result == {"ok": True}
    assert attempts["count"] == 2
    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_make_blockscout_post_request_retries_on_connect_timeout():
    attempts = {"count": 0}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *_args, **_kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ConnectTimeout("connect timeout")
            return MockResponse({"ok": True})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        result = await make_blockscout_post_request("1", "/b", {"x": 1})
    assert result == {"ok": True}
    assert attempts["count"] == 2
    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_make_blockscout_post_request_does_not_retry_on_read_timeout():
    attempts = {"count": 0}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *_args, **_kwargs):
            attempts["count"] += 1
            raise httpx.ReadTimeout("read timeout")

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        with pytest.raises(httpx.ReadTimeout):
            await make_blockscout_post_request("1", "/b", {"x": 1})
    assert attempts["count"] == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_make_blockscout_post_request_does_not_retry_on_read_error():
    attempts = {"count": 0}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *_args, **_kwargs):
            attempts["count"] += 1
            raise httpx.ReadError("read error")

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        with pytest.raises(httpx.ReadError):
            await make_blockscout_post_request("1", "/b", {"x": 1})
    assert attempts["count"] == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_make_blockscout_post_request_does_not_retry_on_http_status_error():
    attempts = {"count": 0}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *_args, **_kwargs):
            attempts["count"] += 1
            return MockResponse({"error": "bad"}, status_code=500)

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await make_blockscout_post_request("1", "/b", {"x": 1})
    assert attempts["count"] == 1
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Authenticated-transport test for POST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_post_request_sends_auth_headers_to_pro_api(monkeypatch):
    """POST requests must carry auth headers and target the PRO API host.

    This complements the GET-side security test in test_common_metadata.py.
    Without this, an implementation could authenticate GET but leave JSON-RPC
    POST unauthenticated and still pass the unit suite.
    """
    monkeypatch.setattr(config, "pro_api_key", "post_test_key")
    chain_id = "1"
    api_path = "/json-rpc"
    pro_base = config.pro_api_base_url

    captured: dict = {}

    class CapturingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params, headers=None, **kwargs):
            captured["url"] = url
            captured["headers"] = headers or {}
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"result": "ok"}, request=request)

    stub_ensure_chain_supported = AsyncMock()

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=CapturingClient()),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", stub_ensure_chain_supported),
    ):
        result = await make_blockscout_post_request(
            chain_id=chain_id,
            api_path=api_path,
            json_body={"jsonrpc": "2.0", "method": "eth_blockNumber", "id": 1},
        )

    assert result == {"result": "ok"}
    stub_ensure_chain_supported.assert_awaited_once_with(chain_id)
    assert captured["url"] == f"{pro_base}/{chain_id}{api_path}"
    assert captured["headers"].get("Authorization") == "Bearer post_test_key"
    assert "User-Agent" in captured["headers"]
    assert captured["headers"].get("Accept") == "application/json"


# ---------------------------------------------------------------------------
# CreditsExhaustedError: POST 402 → distinct error, no retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_post_request_402_raises_credits_exhausted_error():
    """A 402 response from POST raises CreditsExhaustedError and is not retried."""
    attempts = {"count": 0}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *_args, **_kwargs):
            attempts["count"] += 1
            return MockResponse({"error": "Out of credits"}, status_code=402)

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
        patch.object(config, "pro_api_key", "test_key"),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        with pytest.raises(CreditsExhaustedError):
            await make_blockscout_post_request("1", "/b", {"x": 1})

    assert attempts["count"] == 1
    mock_sleep.assert_not_called()
