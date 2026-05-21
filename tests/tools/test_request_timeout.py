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
