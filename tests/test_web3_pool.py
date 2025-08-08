from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockscout_mcp_server.web3_pool import (
    AsyncHTTPProviderBlockscout,
    Web3Pool,
)


@pytest.mark.asyncio
async def test_web3_pool_reuses_instances():
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    with (
        patch(
            "blockscout_mcp_server.web3_pool.get_blockscout_base_url",
            new_callable=AsyncMock,
            return_value="https://example.org",
        ) as mock_get_url,
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session) as mock_session_cls,
    ):
        w3_first = await pool.get("1")
        w3_second = await pool.get("1")
    assert w3_first is w3_second
    mock_get_url.assert_called_once_with("1")
    mock_session_cls.assert_called_once()
    assert w3_first.provider.endpoint_uri == "https://example.org/api/eth-rpc"


@pytest.mark.asyncio
async def test_provider_formats_request():
    provider = AsyncHTTPProviderBlockscout(endpoint_uri="http://rpc", request_kwargs={})
    session_mock = MagicMock()
    session_mock.closed = False
    provider.set_pooled_session(session_mock)
    with patch.object(provider, "_make_http_request", new_callable=AsyncMock, return_value={}) as mock_http:
        await provider.make_request("eth_method", ("0xabc",))
        await provider.make_request("eth_method", ["0xdef", "latest"])
    first_rpc = mock_http.await_args_list[0].args[1]
    second_rpc = mock_http.await_args_list[1].args[1]
    assert first_rpc["params"] == ["0xabc"]
    assert first_rpc["id"] == 1
    assert second_rpc["params"] == ["0xdef", "latest"]
    assert second_rpc["id"] == 2
