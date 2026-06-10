# SPDX-License-Identifier: LicenseRef-Blockscout
"""Auth-matrix tests for make_blockscout_request (GET helper) in tools/common.py.

Covers client-key precedence, serverless mode, fallback, malformed-key fail-fast,
no-fallback-on-upstream-rejection, and ContextVar propagation through
make_request_with_periodic_progress.

These scenarios are kept separate from the broader transport/error tests in
test_common_blockscout_request.py to stay within the 500 LOC ceiling (rule 210).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import _client_key_state, _Valid
from blockscout_mcp_server.tools.common import make_blockscout_request, make_request_with_periodic_progress

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_DEFAULT_URL = "https://api.blockscout.com/1/api/v2/test"
_CHAIN_ID = "1"
_API_PATH = "/api/v2/test"


def _ok_response(url: str = _DEFAULT_URL) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(200, json={"result": "ok"}, request=request)


def _error_response(status_code: int, url: str = _DEFAULT_URL) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, content=b"Rejected", request=request)


class CapturingClient:
    """Fake httpx.AsyncClient that records the URL and headers from .get()."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.get_url: str | None = None
        self.get_headers: dict = {}
        self.call_count = 0

    async def __aenter__(self) -> "CapturingClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, params=None, headers=None, **kwargs) -> httpx.Response:
        self.call_count += 1
        self.get_url = url
        self.get_headers = dict(headers or {})
        return self._response


class NeverCalledClient:
    """Fake client that fails the test if any HTTP method is invoked."""

    async def __aenter__(self) -> "NeverCalledClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, *args, **kwargs):
        raise AssertionError("HTTP client should not have been called")


# ---------------------------------------------------------------------------
# 1. Client key overrides server key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_key_overrides_server_key(monkeypatch):
    """GET sends the client key even when config.pro_api_key holds a different server key."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")
    fake_client = CapturingClient(_ok_response())
    token = _client_key_state.set(_Valid(value="client-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            result = await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)
    finally:
        _client_key_state.reset(token)

    assert result == {"result": "ok"}
    assert fake_client.get_headers.get("Authorization") == "Bearer client-key"


# ---------------------------------------------------------------------------
# 2. Serverless mode: empty server key + valid client key succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_serverless_mode_valid_client_key(monkeypatch):
    """With empty server key and valid client key, GET sends client-key Authorization and succeeds."""
    monkeypatch.setattr(config, "pro_api_key", "")
    fake_client = CapturingClient(_ok_response())
    token = _client_key_state.set(_Valid(value="client-only-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            result = await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)
    finally:
        _client_key_state.reset(token)

    assert result == {"result": "ok"}
    assert fake_client.get_headers.get("Authorization") == "Bearer client-only-key"


# ---------------------------------------------------------------------------
# 3. Absent client key falls back to server key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_falls_back_to_server_key_when_client_key_absent(monkeypatch):
    """With no ContextVar and config.pro_api_key set, GET sends the server key."""
    monkeypatch.setattr(config, "pro_api_key", "server-only-key")
    fake_client = CapturingClient(_ok_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        result = await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)

    assert result == {"result": "ok"}
    assert fake_client.get_headers.get("Authorization") == "Bearer server-only-key"


# ---------------------------------------------------------------------------
# 4. Malformed client key fails before any HTTP call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_malformed_client_key_raises_before_http_call(monkeypatch):
    """With a malformed client key in the ContextVar, GET raises ValueError before any HTTP call."""
    from blockscout_mcp_server.pro_api_key_context import _Malformed

    monkeypatch.setattr(config, "pro_api_key", "server-key")
    token = _client_key_state.set(_Malformed())
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=NeverCalledClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            with pytest.raises(ValueError, match="malformed"):
                await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)
    finally:
        _client_key_state.reset(token)


# ---------------------------------------------------------------------------
# 5. No fallback on upstream-rejected key (well-formed client key, upstream 401)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_no_fallback_on_upstream_rejection(monkeypatch):
    """GET makes exactly one request with the client key and propagates HTTPStatusError on upstream 401."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")

    attempt_count = {"n": 0}
    captured_headers: list[dict] = []

    class _RejectingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None, **kwargs):
            attempt_count["n"] += 1
            captured_headers.append(dict(headers or {}))
            request = httpx.Request("GET", url)
            return httpx.Response(401, content=b"Unauthorized", request=request)

    token = _client_key_state.set(_Valid(value="well-formed-client-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_RejectingClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)
    finally:
        _client_key_state.reset(token)

    # Must make exactly one call, with the client key (not a second attempt with the server key)
    assert attempt_count["n"] == 1
    assert captured_headers[0].get("Authorization") == "Bearer well-formed-client-key"


# ---------------------------------------------------------------------------
# 6. Both keys absent raises not-configured ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_raises_not_configured_when_both_keys_absent(monkeypatch):
    """With no client key and empty server key, GET raises the not-configured ValueError."""
    monkeypatch.setattr(config, "pro_api_key", "")
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=NeverCalledClient()),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        with pytest.raises(ValueError, match="PRO API key required"):
            await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)


# ---------------------------------------------------------------------------
# 7. ContextVar propagates into make_request_with_periodic_progress child task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_context_var_propagates_into_periodic_progress_task(monkeypatch):
    """A key set in ContextVar is observed by the request function spawned via make_request_with_periodic_progress."""
    monkeypatch.setattr(config, "pro_api_key", "server-key")
    fake_client = CapturingClient(_ok_response())
    token = _client_key_state.set(_Valid(value="propagated-client-key"))
    try:
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        ):
            mock_ctx = MagicMock()
            mock_ctx.report_progress = AsyncMock()

            result = await make_request_with_periodic_progress(
                ctx=mock_ctx,
                request_function=make_blockscout_request,
                request_args={"chain_id": _CHAIN_ID, "api_path": _API_PATH},
                total_duration_hint=30.0,
            )
    finally:
        _client_key_state.reset(token)

    assert result == {"result": "ok"}
    # Progress beats must have been emitted along the periodic-progress path.
    mock_ctx.report_progress.assert_awaited()
    # The key must have been visible inside the spawned child task
    assert fake_client.get_headers.get("Authorization") == "Bearer propagated-client-key"


# ---------------------------------------------------------------------------
# 8. Secret not in exception message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_malformed_key_not_in_exception_message(monkeypatch):
    """The ValueError for a malformed key must not contain the raw submitted key value."""
    from blockscout_mcp_server.pro_api_key_context import _Malformed

    monkeypatch.setattr(config, "pro_api_key", "server-key")
    # Simulate a raw key that was submitted but failed validation
    # We set _Malformed state (since _normalize_key already stripped the value)
    token = _client_key_state.set(_Malformed())
    try:
        with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=NeverCalledClient()):
            with pytest.raises(ValueError) as exc_info:
                await make_blockscout_request(chain_id=_CHAIN_ID, api_path=_API_PATH)
    finally:
        _client_key_state.reset(token)

    # The exception message must not leak any key material
    error_message = str(exc_info.value)
    # The _Malformed state carries no raw value, so this verifies the message
    # describes the error without echoing raw input.
    assert "Bearer" not in error_message
    assert "server-key" not in error_message
