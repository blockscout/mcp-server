# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import _client_key_state, _Valid
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
# Phase 4: POST auth matrix (client-key precedence, serverless mode, etc.)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_client_key_overrides_server_key(monkeypatch):
    """POST sends the client key even when config.pro_api_key holds a different server key."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")
    captured: dict = {}

    class CapturingPostClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params, headers=None, **kwargs):
            captured["headers"] = dict(headers or {})
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"result": "ok"}, request=request)

    token = _client_key_state.set(_Valid(value="client-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=CapturingPostClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            result = await make_blockscout_post_request("1", "/json-rpc", {"x": 1})
    finally:
        _client_key_state.reset(token)

    assert result == {"result": "ok"}
    assert captured["headers"].get("Authorization") == "Bearer client-key"


@pytest.mark.asyncio
async def test_post_serverless_mode_valid_client_key(monkeypatch):
    """With empty server key and valid client key in ContextVar, POST sends client-key Authorization and succeeds."""
    monkeypatch.setattr(config, "pro_api_key", "")
    captured: dict = {}

    class CapturingPostClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params, headers=None, **kwargs):
            captured["headers"] = dict(headers or {})
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"result": "ok"}, request=request)

    token = _client_key_state.set(_Valid(value="client-only-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=CapturingPostClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            result = await make_blockscout_post_request("1", "/json-rpc", {"x": 1})
    finally:
        _client_key_state.reset(token)

    assert result == {"result": "ok"}
    assert captured["headers"].get("Authorization") == "Bearer client-only-key"


@pytest.mark.asyncio
async def test_post_falls_back_to_server_key_when_client_absent(monkeypatch):
    """With no ContextVar and config.pro_api_key set, POST sends the server key."""
    monkeypatch.setattr(config, "pro_api_key", "server-only-key")
    captured: dict = {}

    class CapturingPostClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params, headers=None, **kwargs):
            captured["headers"] = dict(headers or {})
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"result": "ok"}, request=request)

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=CapturingPostClient()),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        result = await make_blockscout_post_request("1", "/json-rpc", {"x": 1})

    assert result == {"result": "ok"}
    assert captured["headers"].get("Authorization") == "Bearer server-only-key"


@pytest.mark.asyncio
async def test_post_malformed_client_key_raises_before_http_call(monkeypatch):
    """With a malformed client key in the ContextVar, POST raises ValueError before any HTTP call."""
    from blockscout_mcp_server.pro_api_key_context import _Malformed

    monkeypatch.setattr(config, "pro_api_key", "server-key")

    class NeverCalledPostClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise AssertionError("HTTP client should not have been called for a malformed key")

    token = _client_key_state.set(_Malformed())
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=NeverCalledPostClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            with pytest.raises(ValueError, match="malformed"):
                await make_blockscout_post_request("1", "/json-rpc", {"x": 1})
    finally:
        _client_key_state.reset(token)


@pytest.mark.asyncio
async def test_post_no_fallback_on_upstream_rejection(monkeypatch):
    """POST makes exactly one request with the client key and propagates HTTPStatusError on upstream 401."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")
    attempt_count = {"n": 0}
    captured_headers: list[dict] = []

    class _RejectingPostClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params, headers=None, **kwargs):
            attempt_count["n"] += 1
            captured_headers.append(dict(headers or {}))
            request = httpx.Request("POST", url)
            return httpx.Response(401, content=b"Unauthorized", request=request)

    token = _client_key_state.set(_Valid(value="well-formed-client-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_RejectingPostClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await make_blockscout_post_request("1", "/json-rpc", {"x": 1})
    finally:
        _client_key_state.reset(token)

    assert attempt_count["n"] == 1
    assert captured_headers[0].get("Authorization") == "Bearer well-formed-client-key"


@pytest.mark.asyncio
async def test_post_raises_not_configured_when_both_keys_absent(monkeypatch):
    """With no client key and empty server key, POST raises the not-configured ValueError."""
    monkeypatch.setattr(config, "pro_api_key", "")

    class NeverCalledPostClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise AssertionError("HTTP client should not have been called when keys are absent")

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=NeverCalledPostClient()),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        with pytest.raises(ValueError, match="BLOCKSCOUT_PRO_API_KEY"):
            await make_blockscout_post_request("1", "/json-rpc", {"x": 1})


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
