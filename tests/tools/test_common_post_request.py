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

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=self)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_make_blockscout_post_request_success_with_params_and_apikey():
    calls = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, params):
            calls.append((url, json, params.copy()))
            return MockResponse({"ok": True})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=Client()),
        patch("blockscout_mcp_server.tools.common.config.bs_api_key", "k"),
    ):
        data = await make_blockscout_post_request("https://a", "/b", {"x": 1}, {"q": "1"})
    assert data == {"ok": True}
    assert calls[0][2]["apikey"] == "k"
