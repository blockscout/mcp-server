# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for _pro_api_headers() and make_metadata_request() in tools/common.py.

Also contains the security regression test proving the PRO API key never
leaks to arbitrary Blockscout explorer instances via make_blockscout_request.
"""

from unittest.mock import patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SERVER_VERSION
from blockscout_mcp_server.tools.common import (
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


# ---------------------------------------------------------------------------
# Security: PRO API key must NOT leak to make_blockscout_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_does_not_send_pro_api_key(monkeypatch):
    """PRO API key must never appear in make_blockscout_request outgoing headers.

    This covers arbitrary / third-party explorer instances whose base URLs
    come from chain config — the highest-risk upstream per issue #375.
    Checks both the AsyncClient constructor kwargs and the per-request
    client.get() kwargs.
    """
    monkeypatch.setattr(config, "pro_api_key", "proapi_test")

    ok_resp = _ok_response("https://example-explorer.test/api/v2/blocks/1")
    fake_client = CapturingAsyncClient(ok_resp)

    # Patch httpx.AsyncClient directly (not _create_httpx_client) so we catch
    # any default-header or auth leak introduced inside _create_httpx_client.
    captured_constructor_kwargs: dict = {}

    class CapturingClientClass:
        """Mimics httpx.AsyncClient at the class level."""

        def __init__(self, **kwargs):
            captured_constructor_kwargs.update(kwargs)

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            return None

    with patch("blockscout_mcp_server.tools.common.httpx.AsyncClient", CapturingClientClass):
        result = await make_blockscout_request(
            base_url="https://example-explorer.test",
            api_path="/api/v2/blocks/1",
        )

    assert result == {"result": "ok"}

    # Constructor must not carry auth material
    assert "Authorization" not in (captured_constructor_kwargs.get("headers") or {})
    assert "auth" not in captured_constructor_kwargs

    # Per-request .get() kwargs must also be clean
    get_kwargs = fake_client.get_kwargs or {}
    assert "Authorization" not in (get_kwargs.get("headers") or {})
    assert "auth" not in get_kwargs
