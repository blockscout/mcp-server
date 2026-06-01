# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from blockscout_mcp_server.config import config
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
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ) as mock_ensure,
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session) as mock_session_cls,
        patch.object(config, "pro_api_key", "test-key"),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3_first = await pool.get("1")
        w3_second = await pool.get("1")
    assert w3_first is w3_second
    mock_ensure.assert_called_with("1")
    assert mock_ensure.call_count == 2
    mock_session_cls.assert_called_once()
    assert w3_first.provider.endpoint_uri == "https://api.blockscout.com/1/json-rpc"


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


@pytest.mark.asyncio
async def test_get_merges_default_headers():
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch(
            "blockscout_mcp_server.web3_pool.aiohttp.ClientSession",
            return_value=mock_session,
        ),
        patch.object(config, "pro_api_key", "test-key"),
    ):
        w3 = await pool.get("1", headers={"X-Test": "abc"})
    hdrs = w3.provider._request_kwargs["headers"]
    assert hdrs["X-Test"] == "abc"
    assert "User-Agent" in hdrs


@pytest.mark.asyncio
async def test_make_http_request_uses_headers_and_timeout():
    provider = AsyncHTTPProviderBlockscout(
        endpoint_uri="http://rpc",
        request_kwargs={"headers": {"User-Agent": "UA"}, "timeout": 10},
    )
    session = MagicMock()
    post_ctx = MagicMock()
    post_ctx.__aenter__ = AsyncMock(return_value=post_ctx)
    post_ctx.__aexit__ = AsyncMock(return_value=None)
    post_ctx.json = AsyncMock(return_value={})
    post_ctx.raise_for_status = MagicMock()
    session.post = MagicMock(return_value=post_ctx)

    await provider._make_http_request(session, {"jsonrpc": "2.0"})

    session.post.assert_called_once()
    _, kwargs = session.post.call_args
    hdrs = kwargs["headers"]
    assert hdrs["User-Agent"] == "UA"
    assert hdrs["Content-Type"] == "application/json"
    assert hdrs["Accept"] == "application/json"
    timeout = kwargs["timeout"]
    assert isinstance(timeout, aiohttp.ClientTimeout)
    assert timeout.total == 10


@pytest.mark.asyncio
async def test_auth_header_in_request_headers_not_in_cache_key():
    """Provider request headers contain Authorization; pool cache key does not."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    api_key = "my-secret-key"
    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
        patch.object(config, "pro_api_key", api_key),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3 = await pool.get("1")

    # Provider request headers must include Authorization
    hdrs = w3.provider._request_kwargs["headers"]
    assert hdrs.get("Authorization") == f"Bearer {api_key}"

    # No cache key in the pool should contain the Authorization value
    for key in pool._pool:
        _chain_id, hdr_items = key
        for hdr_name, hdr_val in hdr_items:
            assert hdr_name.lower() != "authorization", "Authorization found in cache key name"
            assert api_key not in hdr_val, "API key found in cache key value"


@pytest.mark.asyncio
async def test_key_rotation_refreshes_auth_on_cache_hit():
    """Key rotation takes effect on the next call even when the provider is cached."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    first_key = "first-token"
    second_key = "second-token"

    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
        patch.object(config, "pro_api_key", first_key),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3_first = await pool.get("1")

    # Rotate the key and call get() again for the same chain
    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
        patch.object(config, "pro_api_key", second_key),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3_second = await pool.get("1")

    # Same provider instance (cache hit)
    assert w3_first is w3_second

    # Auth header must reflect the second (rotated) key
    hdrs = w3_second.provider._request_kwargs["headers"]
    assert hdrs.get("Authorization") == f"Bearer {second_key}"
    assert f"Bearer {first_key}" not in hdrs.get("Authorization", "")

    # Cache key must not contain either token
    for key in pool._pool:
        _chain_id, hdr_items = key
        for hdr_name, hdr_val in hdr_items:
            assert hdr_name.lower() != "authorization"
            assert first_key not in hdr_val
            assert second_key not in hdr_val


@pytest.mark.asyncio
async def test_caller_authorization_is_sanitized():
    """Caller-supplied Authorization is replaced by config key; X-Test is preserved."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    config_key = "config-api-key"
    caller_token = "caller-secret"

    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
        patch.object(config, "pro_api_key", config_key),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3 = await pool.get("1", headers={"Authorization": f"Bearer {caller_token}", "X-Test": "abc"})

    # No cache key should contain the caller's token or an Authorization entry
    for key in pool._pool:
        _chain_id, hdr_items = key
        for hdr_name, hdr_val in hdr_items:
            assert hdr_name.lower() != "authorization", "Authorization found in cache key"
            assert caller_token not in hdr_val, "Caller token found in cache key value"

    # Provider request headers must carry the config key, not the caller token
    hdrs = w3.provider._request_kwargs["headers"]
    assert hdrs.get("Authorization") == f"Bearer {config_key}"
    assert caller_token not in hdrs.get("Authorization", "")

    # Custom X-Test header must be preserved in both cache key and request headers
    assert hdrs.get("X-Test") == "abc"
    found_x_test_in_key = False
    for key in pool._pool:
        _chain_id, hdr_items = key
        for hdr_name, hdr_val in hdr_items:
            if hdr_name == "X-Test" and hdr_val == "abc":
                found_x_test_in_key = True
    assert found_x_test_in_key, "X-Test header not found in cache key"


@pytest.mark.asyncio
async def test_no_key_raises_value_error():
    """get() raises ValueError immediately when no PRO API key is configured."""
    pool = Web3Pool()
    ensure_mock = AsyncMock()
    session_cls_mock = MagicMock()

    with (
        patch("blockscout_mcp_server.web3_pool.ensure_chain_supported", ensure_mock),
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", session_cls_mock),
        patch.object(config, "pro_api_key", ""),
    ):
        with pytest.raises(ValueError, match="BLOCKSCOUT_PRO_API_KEY"):
            await pool.get("1")

    ensure_mock.assert_not_called()
    session_cls_mock.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_chain_supported_is_awaited_with_chain_id():
    """ensure_chain_supported is called with the requested chain_id."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ) as mock_ensure,
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
        patch.object(config, "pro_api_key", "some-key"),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        await pool.get("42161")

    mock_ensure.assert_awaited_once_with("42161")
