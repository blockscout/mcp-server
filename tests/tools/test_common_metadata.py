# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for _pro_api_headers() and make_metadata_request() in tools/common.py.

Also contains the security regression test proving the PRO API key is sent
to the PRO API host via make_blockscout_request (now PRO-API routed).
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SERVER_VERSION
from blockscout_mcp_server.pro_api_key_context import _client_key_state, _Valid
from blockscout_mcp_server.tools.common import (
    CreditsExhaustedError,
    _pro_api_headers,
    make_blockscout_request,
    make_metadata_request,
)

# ---------------------------------------------------------------------------
# Capturing fake httpx.AsyncClient
# ---------------------------------------------------------------------------


class CapturingAsyncClient:
    """Fake httpx.AsyncClient that records constructor kwargs and get() kwargs.

    Used to assert what headers (and other kwargs) are passed to both the
    client constructor and the per-request .get() call.
    """

    def __init__(self, response: httpx.Response, **constructor_kwargs):
        self._response = response
        self.constructor_kwargs = constructor_kwargs
        self.get_kwargs: dict | None = None
        self.get_url: str | None = None

    async def __aenter__(self) -> "CapturingAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, **kwargs) -> httpx.Response:
        self.get_url = url
        self.get_kwargs = kwargs
        return self._response


def _ok_response(url: str = "https://example.com") -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(200, json={"result": "ok"}, request=request)


def _error_response(status_code: int, url: str = "https://example.com") -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, content=b"Unauthorized", request=request)


# ---------------------------------------------------------------------------
# _pro_api_headers() tests
# ---------------------------------------------------------------------------


def test_pro_api_headers_with_key(monkeypatch):
    """_pro_api_headers() includes Authorization Bearer and User-Agent/Accept when key is set."""
    monkeypatch.setattr(config, "pro_api_key", "test_secret_key")
    headers = _pro_api_headers()
    assert headers["Authorization"] == "Bearer test_secret_key"
    assert "User-Agent" in headers
    assert f"/{SERVER_VERSION}" in headers["User-Agent"]
    assert headers["Accept"] == "application/json"


def test_pro_api_headers_without_key(monkeypatch):
    """_pro_api_headers() omits Authorization but keeps User-Agent/Accept when key is empty."""
    monkeypatch.setattr(config, "pro_api_key", "")
    headers = _pro_api_headers()
    assert "Authorization" not in headers
    assert "User-Agent" in headers
    assert headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# make_metadata_request() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_metadata_request_uses_pro_api_base_url_and_auth_headers(monkeypatch):
    """make_metadata_request GETs config.pro_api_base_url + api_path with auth headers."""
    monkeypatch.setattr(config, "pro_api_key", "api_key_12345")
    pro_base = config.pro_api_base_url  # e.g. "https://api.blockscout.com"
    api_path = "/api/v1/metadata/address"
    params = {"address": "0xabc"}

    fake_client = CapturingAsyncClient(_ok_response(pro_base + api_path))

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client):
        result = await make_metadata_request(api_path, params)

    assert result == {"result": "ok"}
    assert fake_client.get_url == f"{pro_base}{api_path}"
    assert fake_client.get_kwargs is not None
    sent_headers = fake_client.get_kwargs.get("headers", {})
    assert sent_headers.get("Authorization") == "Bearer api_key_12345"
    assert "User-Agent" in sent_headers
    assert sent_headers.get("Accept") == "application/json"
    assert fake_client.get_kwargs.get("params") == params


@pytest.mark.asyncio
async def test_make_metadata_request_propagates_http_status_error(monkeypatch):
    """make_metadata_request raises HTTPStatusError on non-2xx (e.g. 401)."""
    monkeypatch.setattr(config, "pro_api_key", "bad_key")
    api_path = "/api/v1/metadata/address"

    fake_client = CapturingAsyncClient(_error_response(401))

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client):
        with pytest.raises(httpx.HTTPStatusError):
            await make_metadata_request(api_path)


@pytest.mark.asyncio
async def test_make_metadata_request_skips_network_when_no_key(monkeypatch):
    """With no PRO API key, make_metadata_request raises before any network call.

    Efficiency guard: a keyless deployment must not issue a request the PRO API
    is guaranteed to reject. The HTTP client must never even be created.
    """
    monkeypatch.setattr(config, "pro_api_key", "")

    def _fail_create_client(*args, **kwargs):
        raise AssertionError("No HTTP client should be created when the PRO API key is absent")

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", _fail_create_client):
        with pytest.raises(ValueError, match="BLOCKSCOUT_PRO_API_KEY"):
            await make_metadata_request("/services/metadata/api/v1/metadata", {"addresses": "0xabc"})


# ---------------------------------------------------------------------------
# New behaviors acquired by routing through _make_blockscout_http_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_metadata_request_uses_metadata_timeout(monkeypatch):
    """make_metadata_request creates the HTTP client with config.metadata_timeout.

    This guards the most likely silent regression: an implementation that forgets
    the explicit timeout= argument and lets the core fall back to config.bs_timeout
    (120s), silently widening the metadata budget from 30s to 120s.
    """
    monkeypatch.setattr(config, "pro_api_key", "api_key_12345")
    api_path = "/api/v1/metadata/address"

    request = httpx.Request("GET", f"{config.pro_api_base_url}{api_path}")
    ok_resp = httpx.Response(200, json={"result": "ok"}, request=request)

    class _MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            return ok_resp

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=_MockClient(),
    ) as mock_create_client:
        await make_metadata_request(api_path)

    mock_create_client.assert_called_once_with(timeout=config.metadata_timeout)


@pytest.mark.asyncio
async def test_make_metadata_request_retries_then_succeeds(monkeypatch):
    """make_metadata_request retries on httpx.RequestError and returns result on success.

    Simulates two transient failures followed by a successful response.
    Asserts that .get() is called exactly 3 times and anyio.sleep is awaited twice
    (once per backoff between attempts).
    The retry cap is pinned to 3 via monkeypatch so the assertion is deterministic.
    """
    monkeypatch.setattr(config, "pro_api_key", "api_key_12345")
    monkeypatch.setattr(config, "bs_request_max_retries", 3)
    api_path = "/api/v1/metadata/address"

    attempt_count = {"n": 0}

    request = httpx.Request("GET", f"{config.pro_api_base_url}{api_path}")
    ok_resp = httpx.Response(200, json={"data": "value"}, request=request)

    class _TransientClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            attempt_count["n"] += 1
            if attempt_count["n"] < 3:
                raise httpx.RequestError("transient error")
            return ok_resp

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_TransientClient()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
    ):
        result = await make_metadata_request(api_path)

    assert result == {"data": "value"}
    assert attempt_count["n"] == 3
    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_make_metadata_request_retry_exhaustion_raises(monkeypatch):
    """make_metadata_request re-raises httpx.RequestError after all retries are exhausted.

    With the retry cap pinned to 3, the client's .get() should be called exactly 3
    times before the error surfaces, and anyio.sleep should be awaited exactly twice.
    """
    monkeypatch.setattr(config, "pro_api_key", "api_key_12345")
    monkeypatch.setattr(config, "bs_request_max_retries", 3)
    api_path = "/api/v1/metadata/address"

    attempt_count = {"n": 0}

    class _AlwaysFailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            attempt_count["n"] += 1
            raise httpx.RequestError("persistent error")

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_AlwaysFailingClient()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
    ):
        with pytest.raises(httpx.RequestError):
            await make_metadata_request(api_path)

    assert attempt_count["n"] == 3
    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_make_metadata_request_null_body_normalized_to_empty_dict(monkeypatch):
    """A JSON null response body is normalized to {} instead of None.

    This prevents a latent AttributeError in the caller (get_address_info calls
    .get("addresses") on the result, which would fail on None).
    """
    monkeypatch.setattr(config, "pro_api_key", "api_key_12345")
    api_path = "/api/v1/metadata/address"

    request = httpx.Request("GET", f"{config.pro_api_base_url}{api_path}")
    # Use content=b"null" so httpx.Response.json() returns Python None (not an empty body).
    null_resp = httpx.Response(200, content=b"null", headers={"content-type": "application/json"}, request=request)

    class _NullBodyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            return null_resp

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_NullBodyClient()):
        result = await make_metadata_request(api_path)

    assert result == {}


@pytest.mark.asyncio
async def test_make_metadata_request_enriched_error_message_and_no_retry_on_http_error(monkeypatch):
    """HTTP error status raises HTTPStatusError with enriched message and is not retried.

    Asserts:
    - The error message contains the status code and 'Details:' segment.
    - The client's .get() is called exactly once (HTTP errors are not retried).
    """
    monkeypatch.setattr(config, "pro_api_key", "bad_key")
    monkeypatch.setattr(config, "bs_request_max_retries", 3)
    api_path = "/api/v1/metadata/address"

    attempt_count = {"n": 0}

    class _UnauthorizedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            attempt_count["n"] += 1
            request = httpx.Request("GET", url)
            return httpx.Response(401, content=b"Unauthorized", request=request)

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_UnauthorizedClient()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_metadata_request(api_path)

    assert "401" in str(exc_info.value)
    assert "Details:" in str(exc_info.value)
    assert attempt_count["n"] == 1
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Security: PRO API key MUST be sent to the PRO API host via make_blockscout_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_sends_pro_api_key_to_pro_api_host(monkeypatch):
    """PRO API key must appear in make_blockscout_request outgoing headers, targeting the PRO API host.

    Now that make_blockscout_request routes through the PRO API, the key must be
    sent as a Bearer token to config.pro_api_base_url (not a third-party URL).
    Checks both the URL and the per-request client.get() kwargs for auth headers.
    """
    monkeypatch.setattr(config, "pro_api_key", "proapi_test")
    chain_id = "1"
    api_path = "/api/v2/blocks/1"
    pro_base = config.pro_api_base_url

    ok_resp = _ok_response(f"{pro_base}/{chain_id}{api_path}")
    fake_client = CapturingAsyncClient(ok_resp)

    stub_ensure_chain_supported = AsyncMock()

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", stub_ensure_chain_supported),
    ):
        result = await make_blockscout_request(chain_id=chain_id, api_path=api_path)

    assert result == {"result": "ok"}

    # ensure_chain_supported must have been called with the correct chain_id
    stub_ensure_chain_supported.assert_awaited_once_with(chain_id)

    # URL must target the PRO API host
    assert fake_client.get_url == f"{pro_base}/{chain_id}{api_path}"

    # Per-request .get() kwargs must carry auth headers
    get_kwargs = fake_client.get_kwargs or {}
    sent_headers = get_kwargs.get("headers") or {}
    assert sent_headers.get("Authorization") == "Bearer proapi_test"
    assert "User-Agent" in sent_headers
    assert sent_headers.get("Accept") == "application/json"


# ---------------------------------------------------------------------------
# Phase 4: _pro_api_headers() and make_metadata_request() with resolved key
# ---------------------------------------------------------------------------


def test_pro_api_headers_client_key_overrides_server_key(monkeypatch):
    """_pro_api_headers() uses the client key when the ContextVar holds a valid key."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")
    token = _client_key_state.set(_Valid(value="client-key"))
    try:
        headers = _pro_api_headers()
    finally:
        _client_key_state.reset(token)
    assert headers["Authorization"] == "Bearer client-key"


def test_pro_api_headers_serverless_client_key(monkeypatch):
    """_pro_api_headers() includes client key Authorization even with empty server key."""
    monkeypatch.setattr(config, "pro_api_key", "")
    token = _client_key_state.set(_Valid(value="client-key-only"))
    try:
        headers = _pro_api_headers()
    finally:
        _client_key_state.reset(token)
    assert headers["Authorization"] == "Bearer client-key-only"


def test_pro_api_headers_falls_back_to_server_key_when_client_absent(monkeypatch):
    """_pro_api_headers() returns the server key when no client key is in the ContextVar."""
    monkeypatch.setattr(config, "pro_api_key", "server-only-key")
    headers = _pro_api_headers()
    assert headers["Authorization"] == "Bearer server-only-key"


def test_pro_api_headers_omits_authorization_when_both_absent(monkeypatch):
    """_pro_api_headers() omits Authorization when both server key and ContextVar are absent."""
    monkeypatch.setattr(config, "pro_api_key", "")
    headers = _pro_api_headers()
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_make_metadata_request_serverless_valid_client_key(monkeypatch):
    """With empty server key and valid client key in ContextVar, make_metadata_request succeeds."""
    monkeypatch.setattr(config, "pro_api_key", "")
    api_path = "/api/v1/metadata/address"

    fake_client = CapturingAsyncClient(_ok_response(config.pro_api_base_url + api_path))
    token = _client_key_state.set(_Valid(value="client-only-key"))
    try:
        with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client):
            result = await make_metadata_request(api_path)
    finally:
        _client_key_state.reset(token)

    assert result == {"result": "ok"}
    sent_headers = (fake_client.get_kwargs or {}).get("headers", {})
    assert sent_headers.get("Authorization") == "Bearer client-only-key"


@pytest.mark.asyncio
async def test_make_metadata_request_raises_malformed_key_before_network(monkeypatch):
    """make_metadata_request raises ValueError for malformed key before any HTTP call."""
    from blockscout_mcp_server.pro_api_key_context import _Malformed

    monkeypatch.setattr(config, "pro_api_key", "server-key")

    def _fail(*args, **kwargs):
        raise AssertionError("No HTTP client should be created for a malformed key")

    token = _client_key_state.set(_Malformed())
    try:
        with patch("blockscout_mcp_server.tools.common._create_httpx_client", _fail):
            with pytest.raises(ValueError, match="malformed"):
                await make_metadata_request("/api/v1/metadata/address")
    finally:
        _client_key_state.reset(token)


@pytest.mark.asyncio
async def test_make_metadata_request_no_fallback_on_upstream_rejection(monkeypatch):
    """With a valid client key and server key both set, an upstream 401 raises HTTPStatusError without retry."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")
    api_path = "/api/v1/metadata/address"

    attempt_count = {"n": 0}
    captured_headers: list[dict] = []

    class _RejectingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            attempt_count["n"] += 1
            captured_headers.append(dict(kwargs.get("headers") or {}))
            request = httpx.Request("GET", url)
            return httpx.Response(401, content=b"Unauthorized", request=request)

    token = _client_key_state.set(_Valid(value="client-key"))
    try:
        with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_RejectingClient()):
            with pytest.raises(httpx.HTTPStatusError):
                await make_metadata_request(api_path)
    finally:
        _client_key_state.reset(token)

    assert attempt_count["n"] == 1
    assert captured_headers[0].get("Authorization") == "Bearer client-key"


# ---------------------------------------------------------------------------
# CreditsExhaustedError: metadata 402 → distinct error, no retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_metadata_request_402_raises_credits_exhausted_error(monkeypatch):
    """A 402 response from make_metadata_request raises CreditsExhaustedError and is not retried."""
    monkeypatch.setattr(config, "pro_api_key", "bad_key")
    monkeypatch.setattr(config, "bs_request_max_retries", 3)
    api_path = "/api/v1/metadata/address"

    attempt_count = {"n": 0}

    class _PaymentRequiredClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            attempt_count["n"] += 1
            request = httpx.Request("GET", url)
            return httpx.Response(402, content=b'{"error": "Out of credits"}', request=request)

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_PaymentRequiredClient()),
        patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep,
    ):
        with pytest.raises(CreditsExhaustedError):
            await make_metadata_request(api_path)

    assert attempt_count["n"] == 1
    mock_sleep.assert_not_called()
