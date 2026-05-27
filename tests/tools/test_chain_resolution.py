# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.cache import ChainCache, ProApiConfigCache
from blockscout_mcp_server.tools import common
from blockscout_mcp_server.tools.common import ChainNotFoundError

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def reset_caches(monkeypatch):
    monkeypatch.setattr(common, "pro_api_config_cache", ProApiConfigCache())
    monkeypatch.setattr(common, "chain_cache", ChainCache())


async def test_fetch_pro_api_config_success():
    with patch("blockscout_mcp_server.tools.common._create_httpx_client") as factory:
        client = AsyncMock()
        response = AsyncMock()
        response.json.return_value = {"chains": {"1": "https://eth.blockscout.com/"}}
        response.raise_for_status.return_value = None
        client.get.return_value = response
        factory.return_value.__aenter__.return_value = client
        result = await common._fetch_pro_api_config()
    assert result == {"1": "https://eth.blockscout.com"}


async def test_fetch_pro_api_config_invalid_payload():
    with patch("blockscout_mcp_server.tools.common._create_httpx_client") as factory:
        client = AsyncMock()
        response = AsyncMock()
        response.json.return_value = {"endpoint_pricing": {}}
        response.raise_for_status.return_value = None
        client.get.return_value = response
        factory.return_value.__aenter__.return_value = client
        with pytest.raises(ValueError, match="missing or invalid 'chains' key"):
            await common._fetch_pro_api_config()


async def test_get_blockscout_base_url_unsupported_chain():
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config", AsyncMock(return_value={"1": "https://eth"})
    ):
        with pytest.raises(ChainNotFoundError):
            await common.get_blockscout_base_url("999999")
