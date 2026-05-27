# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import patch

import httpx
import pytest

from blockscout_mcp_server.tools.common import make_blockscout_post_request


class MockResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
        self.reason_phrase = "OK"
        self.request = httpx.Request("POST", "https://example.com")
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

        async def post(self, url, json, params):
            calls.append((url, json, params.copy()))
            return MockResponse({"ok": True})

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()):
        data = await make_blockscout_post_request("https://a", "/b", {"x": 1}, {"q": "1"})
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
    ):
        result = await make_blockscout_post_request("https://a", "/b", {"x": 1})
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
    ):
        result = await make_blockscout_post_request("https://a", "/b", {"x": 1})
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
    ):
        with pytest.raises(httpx.ReadTimeout):
            await make_blockscout_post_request("https://a", "/b", {"x": 1})
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
    ):
        with pytest.raises(httpx.ReadError):
            await make_blockscout_post_request("https://a", "/b", {"x": 1})
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
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await make_blockscout_post_request("https://a", "/b", {"x": 1})
    assert attempts["count"] == 1
    mock_sleep.assert_not_called()
