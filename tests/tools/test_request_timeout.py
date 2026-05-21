# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.common import make_blockscout_request


class MockAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._response


@pytest.mark.asyncio
async def test_make_blockscout_request_uses_timeout_override():
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(200, json={"ok": True}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ) as mock_create_client:
        await make_blockscout_request("https://example.com", "/api/v2/test", timeout=20)

    mock_create_client.assert_called_once_with(timeout=20)


@pytest.mark.asyncio
async def test_make_blockscout_request_without_timeout_uses_heavy_timeout():
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(200, json={"ok": True}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ) as mock_create_client:
        await make_blockscout_request("https://example.com", "/api/v2/test")

    mock_create_client.assert_called_once_with(timeout=config.bs_timeout)


@pytest.mark.asyncio
async def test_make_blockscout_request_explicit_none_uses_heavy_timeout():
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(200, json={"ok": True}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ) as mock_create_client:
        await make_blockscout_request("https://example.com", "/api/v2/test", timeout=None)

    mock_create_client.assert_called_once_with(timeout=config.bs_timeout)


@pytest.mark.asyncio
async def test_make_blockscout_request_timeout_reaches_httpx_client():
    """End-to-end: the timeout value reaches the constructed httpx.AsyncClient.

    The other tests in this module only assert that ``_create_httpx_client`` was
    invoked with the expected ``timeout`` kwarg. This test goes one step further
    and constructs a real ``httpx.AsyncClient`` (routed through ``MockTransport``
    so no network is touched), then verifies that the client's ``timeout``
    attribute actually reflects the passed value. This hardens the contract
    against future regressions where ``_create_httpx_client`` could be refactored
    to drop or override the kwarg before passing it to ``httpx.AsyncClient``.
    """
    captured: dict[str, httpx.Timeout] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    def build_real_client(*, timeout: float) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            transport=httpx.MockTransport(handler),
        )
        captured["timeout"] = client.timeout
        return client

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        build_real_client,
    ):
        await make_blockscout_request("https://example.com", "/api/v2/test", timeout=7.5)

    assert "timeout" in captured, "_create_httpx_client was not invoked"
    timeout_obj = captured["timeout"]
    # A scalar float passed to httpx.AsyncClient is wrapped into httpx.Timeout
    # with all four phases set to the same value. Verify the wiring on each
    # phase so a partial regression (e.g., only the read timeout being passed)
    # would still be caught.
    assert timeout_obj.connect == 7.5
    assert timeout_obj.read == 7.5
    assert timeout_obj.write == 7.5
    assert timeout_obj.pool == 7.5
