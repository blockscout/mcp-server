# SPDX-License-Identifier: LicenseRef-Blockscout
import asyncio
import contextvars
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import _client_key_state, _Valid
from blockscout_mcp_server.web3_pool import (
    AsyncHTTPProviderBlockscout,
    Web3Pool,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_post_mock(captured_headers: list[dict]) -> MagicMock:
    """Return a session.post mock that records the headers kwarg on each call."""

    def _post(*args, **kwargs):
        captured_headers.append(dict(kwargs.get("headers", {})))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=None)
        ctx.json = AsyncMock(return_value={})
        ctx.raise_for_status = MagicMock()
        return ctx

    mock = MagicMock(side_effect=_post)
    return mock


# ---------------------------------------------------------------------------
# Existing tests (updated where needed)
# ---------------------------------------------------------------------------


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
    # Authorization must NOT be stored on the provider
    assert "Authorization" not in hdrs


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

    with patch.object(config, "pro_api_key", ""):
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


# ---------------------------------------------------------------------------
# Auth-specific tests (updated to new injection point)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_header_in_request_headers_not_in_cache_key():
    """Auth is injected at request time; cache key and stored provider headers contain no Authorization."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    api_key = "my-secret-key"
    captured: list[dict] = []
    mock_session.post = _make_post_mock(captured)

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
        # Make an actual request so _make_http_request is exercised
        await w3.provider._make_http_request(mock_session, {"jsonrpc": "2.0", "id": 1})

    # Provider stored headers must NOT include Authorization
    stored_hdrs = w3.provider._request_kwargs["headers"]
    assert "Authorization" not in stored_hdrs

    # The outgoing request must carry Authorization: Bearer <key>
    assert len(captured) == 1
    assert captured[0].get("Authorization") == f"Bearer {api_key}"

    # No cache key in the pool should contain the Authorization value
    for cache_key in pool._pool:
        _chain_id, hdr_items = cache_key
        for hdr_name, hdr_val in hdr_items:
            assert hdr_name.lower() != "authorization", "Authorization found in cache key name"
            assert api_key not in hdr_val, "API key found in cache key value"


@pytest.mark.asyncio
async def test_changed_key_is_reapplied_on_cache_hit():
    """On a cache hit, the outgoing request reflects the currently-effective key (resolved per request)."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    first_key = "first-token"
    second_key = "second-token"
    captured: list[dict] = []
    mock_session.post = _make_post_mock(captured)

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
        await w3_first.provider._make_http_request(mock_session, {"jsonrpc": "2.0", "id": 1})

    # Change the configured key and call get() again for the same chain (cache hit)
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
        await w3_second.provider._make_http_request(mock_session, {"jsonrpc": "2.0", "id": 2})

    # Same provider instance (cache hit)
    assert w3_first is w3_second

    # Provider stored headers still have no Authorization
    stored_hdrs = w3_second.provider._request_kwargs["headers"]
    assert "Authorization" not in stored_hdrs

    # First request carried first_key, second request carried second_key
    assert len(captured) == 2
    assert captured[0].get("Authorization") == f"Bearer {first_key}"
    assert captured[1].get("Authorization") == f"Bearer {second_key}"

    # Cache key must not contain either token
    for cache_key in pool._pool:
        _chain_id, hdr_items = cache_key
        for hdr_name, hdr_val in hdr_items:
            assert hdr_name.lower() != "authorization"
            assert first_key not in hdr_val
            assert second_key not in hdr_val


@pytest.mark.asyncio
async def test_caller_authorization_is_sanitized():
    """Caller-supplied Authorization is stripped; only the resolver's key is emitted at request time."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    config_key = "config-api-key"
    caller_token = "caller-secret"
    captured: list[dict] = []
    mock_session.post = _make_post_mock(captured)

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
        await w3.provider._make_http_request(mock_session, {"jsonrpc": "2.0", "id": 1})

    # No cache key should contain the caller's token or an Authorization entry
    for cache_key in pool._pool:
        _chain_id, hdr_items = cache_key
        for hdr_name, hdr_val in hdr_items:
            assert hdr_name.lower() != "authorization", "Authorization found in cache key"
            assert caller_token not in hdr_val, "Caller token found in cache key value"

    # Provider stored headers must NOT carry Authorization at all
    stored_hdrs = w3.provider._request_kwargs["headers"]
    assert "Authorization" not in stored_hdrs
    assert caller_token not in str(stored_hdrs)

    # Custom X-Test header must be preserved in both cache key and stored headers
    assert stored_hdrs.get("X-Test") == "abc"
    found_x_test_in_key = False
    for cache_key in pool._pool:
        _chain_id, hdr_items = cache_key
        for hdr_name, hdr_val in hdr_items:
            if hdr_name == "X-Test" and hdr_val == "abc":
                found_x_test_in_key = True
    assert found_x_test_in_key, "X-Test header not found in cache key"

    # The outgoing request must carry the config key, not the caller token
    assert len(captured) == 1
    assert captured[0].get("Authorization") == f"Bearer {config_key}"
    assert caller_token not in captured[0].get("Authorization", "")


@pytest.mark.asyncio
async def test_no_key_raises_value_error():
    """get() raises ValueError immediately when no effective PRO API key is available."""
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


@pytest.mark.asyncio
async def test_different_chains_share_one_session():
    """Two get() calls for different chain ids create ClientSession exactly once."""
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
        ) as mock_session_cls,
        patch.object(config, "pro_api_key", "test-key"),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3_chain1 = await pool.get("1")
        w3_chain2 = await pool.get("137")

    # ClientSession must be constructed exactly once across both calls
    mock_session_cls.assert_called_once()
    # But the two chains produce distinct provider instances
    assert w3_chain1 is not w3_chain2
    assert w3_chain1.provider.endpoint_uri == "https://api.blockscout.com/1/json-rpc"
    assert w3_chain2.provider.endpoint_uri == "https://api.blockscout.com/137/json-rpc"


@pytest.mark.asyncio
async def test_same_chain_returns_same_provider():
    """get() for the same chain id twice returns the same provider instance."""
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
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        w3_first = await pool.get("1")
        w3_second = await pool.get("1")

    assert w3_first is w3_second


@pytest.mark.asyncio
async def test_close_clears_session_and_new_get_creates_fresh_session():
    """close() closes the shared session; a subsequent get() lazily creates a new one."""
    pool = Web3Pool()

    first_session = MagicMock()
    first_session.closed = False
    first_session.close = AsyncMock()

    second_session = MagicMock()
    second_session.closed = False
    second_session.close = AsyncMock()

    session_side_effects = [first_session, second_session]

    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch(
            "blockscout_mcp_server.web3_pool.aiohttp.ClientSession",
            side_effect=session_side_effects,
        ) as mock_session_cls,
        patch.object(config, "pro_api_key", "test-key"),
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        await pool.get("1")

        # Simulate close
        await pool.close()

        # After close, session field must be reset and pool cleared
        assert pool._session is None
        assert len(pool._pool) == 0
        first_session.close.assert_awaited_once()

        # A subsequent get() must create a brand-new session
        await pool.get("1")

    assert mock_session_cls.call_count == 2
    assert pool._session is second_session


# ---------------------------------------------------------------------------
# New tests required by Phase 5
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serverless_mode_client_key_only():
    """Empty server key + valid client key in ContextVar: get() does not raise, request carries client key."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False
    client_key = "client-only-key"
    captured: list[dict] = []
    mock_session.post = _make_post_mock(captured)

    # Set the ContextVar to a valid client key
    token = _client_key_state.set(_Valid(value=client_key))
    try:
        with (
            patch(
                "blockscout_mcp_server.web3_pool.ensure_chain_supported",
                new_callable=AsyncMock,
            ),
            patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
            patch.object(config, "pro_api_key", ""),  # empty server key
            patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
        ):
            # Should not raise even though server key is empty
            w3 = await pool.get("1")
            await w3.provider._make_http_request(mock_session, {"jsonrpc": "2.0", "id": 1})
    finally:
        _client_key_state.reset(token)

    assert len(captured) == 1
    assert captured[0].get("Authorization") == f"Bearer {client_key}"


@pytest.mark.asyncio
async def test_concurrency_no_cross_contamination():
    """Two concurrent requests to the same chain under different client keys each carry their own key."""
    pool = Web3Pool()
    mock_session = MagicMock()
    mock_session.closed = False

    key_a = "client-key-A"
    key_b = "client-key-B"

    # captured_a / captured_b record headers from each task's request
    captured_a: list[dict] = []
    captured_b: list[dict] = []

    async def run_request_in_context(client_key: str, captured: list[dict]) -> None:
        """Run a single _make_http_request inside a copy of the current context."""
        token = _client_key_state.set(_Valid(value=client_key))
        try:
            # Obtain (or reuse) the pooled provider
            w3 = await pool.get("1")
            # Build a session mock that records to the caller's captured list
            local_session = MagicMock()
            local_session.post = _make_post_mock(captured)
            await w3.provider._make_http_request(local_session, {"jsonrpc": "2.0", "id": 1})
        finally:
            _client_key_state.reset(token)

    with (
        patch(
            "blockscout_mcp_server.web3_pool.ensure_chain_supported",
            new_callable=AsyncMock,
        ),
        patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
        patch.object(config, "pro_api_key", ""),  # no server key — only client keys matter
        patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
    ):
        # Pre-populate pool with a valid key so get() doesn't raise on the empty server key
        seed_token = _client_key_state.set(_Valid(value=key_a))
        try:
            await pool.get("1")
        finally:
            _client_key_state.reset(seed_token)

        # Now run two concurrent tasks under their respective client keys
        ctx_a = contextvars.copy_context()
        ctx_b = contextvars.copy_context()

        task_a = asyncio.ensure_future(ctx_a.run(run_request_in_context, key_a, captured_a))
        task_b = asyncio.ensure_future(ctx_b.run(run_request_in_context, key_b, captured_b))

        await asyncio.gather(task_a, task_b)

    # Each task must have seen its own key — no cross-contamination
    assert len(captured_a) == 1, "Task A did not record exactly one request"
    assert len(captured_b) == 1, "Task B did not record exactly one request"
    assert captured_a[0].get("Authorization") == f"Bearer {key_a}", "Task A carried wrong key"
    assert captured_b[0].get("Authorization") == f"Bearer {key_b}", "Task B carried wrong key"


@pytest.mark.asyncio
async def test_no_fallback_on_upstream_rejection():
    """With a valid client key, an HTTP rejection propagates and no retry with the server key is issued."""
    pool = Web3Pool()
    client_key = "well-formed-client-key"
    server_key = "server-key-different"
    captured: list[dict] = []

    # Session.post returns an async context manager whose __aenter__ raises to simulate a 401 rejection
    def _failing_post(*args, **kwargs):
        captured.append(dict(kwargs.get("headers", {})))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=aiohttp.ClientResponseError(MagicMock(), MagicMock(), status=401))
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post = MagicMock(side_effect=_failing_post)

    token = _client_key_state.set(_Valid(value=client_key))
    try:
        with (
            patch(
                "blockscout_mcp_server.web3_pool.ensure_chain_supported",
                new_callable=AsyncMock,
            ),
            patch("blockscout_mcp_server.web3_pool.aiohttp.ClientSession", return_value=mock_session),
            patch.object(config, "pro_api_key", server_key),
            patch.object(config, "pro_api_base_url", "https://api.blockscout.com"),
        ):
            w3 = await pool.get("1")
            with pytest.raises(aiohttp.ClientResponseError) as exc_info:
                await w3.provider._make_http_request(mock_session, {"jsonrpc": "2.0", "id": 1})
    finally:
        _client_key_state.reset(token)

    # Error must propagate (no swallowing)
    assert exc_info.value.status == 401

    # Exactly one request was issued — no retry with the server key
    assert len(captured) == 1, "Expected exactly one request (no retry)"

    # The request carried the client key, not the server key
    assert captured[0].get("Authorization") == f"Bearer {client_key}"
    assert server_key not in captured[0].get("Authorization", "")
