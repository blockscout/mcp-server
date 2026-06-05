# SPDX-License-Identifier: LicenseRef-Blockscout
"""Async Web3 connection pool optimized for Blockscout RPC.

The custom provider in this module normalizes JSON-RPC parameters and enforces
non-zero request IDs. Blockscout rejects requests with ``id=0`` and parameters
that are not JSON arrays. By reusing a shared ``aiohttp.ClientSession`` across
calls we avoid repeated TCP handshakes and control concurrency via environment
variables:

* ``BLOCKSCOUT_RPC_REQUEST_TIMEOUT`` – seconds before an RPC call times out
* ``BLOCKSCOUT_RPC_POOL_PER_HOST`` – maximum open HTTP connections

Increase this limit for high-throughput deployments or relax it to conserve
resources on constrained hosts. Extend the timeout if the remote Blockscout
instance is slow or under heavy load. The ``BLOCKSCOUT_MCP_USER_AGENT`` variable
customizes the leading part of the ``User-Agent`` header; the server version is
appended automatically.

Authorization is injected at request time inside
:meth:`AsyncHTTPProviderBlockscout._make_http_request` by calling
:func:`~blockscout_mcp_server.pro_api_key_context.resolve_pro_api_key`.  This
means each in-flight request resolves the effective key from the request-scoped
``ContextVar`` rather than reading it from the shared provider instance, so two
concurrent requests with different client keys cannot cross-contaminate each
other's headers.
"""

from __future__ import annotations

import asyncio
from itertools import count
from typing import Any

import aiohttp
from web3 import AsyncWeb3
from web3.providers.rpc import AsyncHTTPProvider

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SERVER_VERSION
from blockscout_mcp_server.pro_api_key_context import require_pro_api_key, resolve_pro_api_key
from blockscout_mcp_server.tools.common import ensure_chain_supported


def _default_headers() -> dict[str, str]:
    """Return the default User-Agent headers, read at call time."""
    return {
        "User-Agent": f"{config.mcp_user_agent}/{SERVER_VERSION} (+pool)",
    }


class AsyncHTTPProviderBlockscout(AsyncHTTPProvider):
    """Custom provider with Blockscout-specific adaptations.

    ``web3.py``'s stock provider doesn't cooperate well with Blockscout's
    JSON-RPC implementation. Blockscout rejects requests with ``id=0`` and
    expects ``params`` to be JSON arrays. The standard provider also manages
    its own ``aiohttp`` sessions, which can reset request IDs when reused.

    This subclass keeps its own ``request_counter`` starting at ``1`` and
    overrides :meth:`make_request` to normalize parameters and inject the
    sequential ID. The :meth:`set_pooled_session` method allows an externally
    managed ``aiohttp.ClientSession`` to be reused for all requests, enabling
    connection pooling and fine-grained timeout control.

    The provider's stored ``_request_kwargs["headers"]`` contain only
    non-secret headers (``User-Agent`` and any caller-supplied non-auth
    headers).  ``Authorization`` is **never** stored on the provider; it is
    resolved at request time inside :meth:`_make_http_request` via
    :func:`~blockscout_mcp_server.pro_api_key_context.resolve_pro_api_key`,
    so concurrent requests each carry their own key without mutating shared
    state.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Start IDs at 1 because Blockscout rejects JSON-RPC requests with id=0
        self.request_counter = count(1)
        # Will be populated by Web3Pool to enable connection reuse
        self.pooled_session: aiohttp.ClientSession | None = None

    def set_pooled_session(self, session: aiohttp.ClientSession) -> None:
        self.pooled_session = session

    async def _make_http_request(self, session: aiohttp.ClientSession, rpc_dict: dict[str, Any]) -> dict[str, Any]:
        """Perform the HTTP request using the given session.

        A dedicated helper lets us share the implementation between pooled and
        fallback sessions while keeping tight control over timeouts.

        ``Authorization`` is injected here at request time by calling
        :func:`~blockscout_mcp_server.pro_api_key_context.resolve_pro_api_key`.
        A fresh header dict is built on every call so the shared provider
        instance is never mutated and concurrent requests remain isolated.
        """
        headers = dict(self._request_kwargs.get("headers", {}))
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")
        # Resolve the effective PRO API key for this specific request.
        # resolve_pro_api_key() raises ValueError for a malformed client key,
        # which propagates out of the JSON-RPC call as the tool error.
        effective_key = resolve_pro_api_key()
        if effective_key:
            headers["Authorization"] = f"Bearer {effective_key}"
        timeout = aiohttp.ClientTimeout(total=self._request_kwargs.get("timeout", config.rpc_request_timeout))
        async with session.post(
            self.endpoint_uri,
            json=rpc_dict,
            headers=headers,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def make_request(self, method: str, params: Any) -> dict[str, Any]:  # type: ignore[override]
        # Blockscout strictly requires ``params`` to be JSON arrays, so normalize
        # iterables or single values into a list.
        if not isinstance(params, list):
            if hasattr(params, "__iter__") and not isinstance(  # noqa: UP038
                params, (str, bytes, dict)
            ):
                params = list(params)
            else:
                params = [params] if params is not None else []

        rpc_dict = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": next(self.request_counter),
        }

        # Prefer the shared session for connection pooling. Fallback to a new
        # session only if the pooled one is unavailable.
        if self.pooled_session and not self.pooled_session.closed:
            return await self._make_http_request(self.pooled_session, rpc_dict)

        async with aiohttp.ClientSession() as session:
            return await self._make_http_request(session, rpc_dict)


class Web3Pool:
    """Manage pooled ``AsyncWeb3`` instances with a single shared session.

    Each unique combination of chain and non-secret headers gets its own
    ``AsyncWeb3`` instance.  All providers share one ``aiohttp.ClientSession``
    so the per-host connection limit becomes a true global cap now that every
    chain's JSON-RPC traffic targets the same host (``api.blockscout.com``).

    Auth headers (``Authorization``) are intentionally excluded from cache
    keys and from the provider's stored headers.  The effective key is resolved
    per request inside :meth:`AsyncHTTPProviderBlockscout._make_http_request`
    via :func:`~blockscout_mcp_server.pro_api_key_context.resolve_pro_api_key`,
    so two concurrent requests against the same pooled provider each carry
    their own key without any shared-state mutation.
    """

    def __init__(self) -> None:
        self._pool: dict[tuple[str, tuple[tuple[str, str], ...]], AsyncWeb3] = {}
        self._session: aiohttp.ClientSession | None = None
        self._session_lock: asyncio.Lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared session, lazily creating it if necessary.

        Uses a double-checked pattern under an ``asyncio.Lock`` so two
        concurrent first-callers cannot create two separate sessions.
        """
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._session_lock:
            # Re-check inside the lock in case another coroutine created it
            # while this one was waiting to acquire.
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    # With a single host the global ``limit`` and the
                    # per-host ``limit_per_host`` are the same cap.
                    connector=aiohttp.TCPConnector(
                        limit=config.rpc_pool_per_host,
                        limit_per_host=config.rpc_pool_per_host,
                    )
                )
        return self._session

    async def get(self, chain_id: str, headers: dict[str, str] | None = None) -> AsyncWeb3:
        # Fail fast when no effective PRO API key is available — no network call
        # should be made when the gateway is guaranteed to reject the request.
        # require_pro_api_key() propagates ValueError for a malformed client
        # key and raises the standard not-configured error when both keys are
        # absent.
        require_pro_api_key("contract reads via the PRO API gateway")

        # Validate the chain before constructing anything.
        await ensure_chain_supported(chain_id)

        # Build non-secret headers for the cache key.  Strip any caller-supplied
        # Authorization so credentials never enter internal dictionaries.
        combined_headers = _default_headers()
        if headers:
            for k, v in headers.items():
                if k.lower() != "authorization":
                    combined_headers[k] = v
        hdr_items = tuple(sorted(combined_headers.items()))
        key = (chain_id, hdr_items)

        session = await self._get_session()

        if key in self._pool:
            w3 = self._pool[key]
            w3.provider.set_pooled_session(session)
            return w3

        endpoint = f"{config.pro_api_base_url}/{chain_id}/json-rpc"

        provider = AsyncHTTPProviderBlockscout(
            endpoint_uri=endpoint,
            request_kwargs={
                "headers": dict(hdr_items),
                "timeout": config.rpc_request_timeout,
            },
        )
        provider.set_pooled_session(session)
        w3 = AsyncWeb3(provider)

        self._pool[key] = w3
        return w3

    async def close(self) -> None:
        for w3 in list(self._pool.values()):
            try:
                await w3.provider.disconnect()
            except Exception:
                pass
        if self._session is not None and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None
        self._pool.clear()


WEB3_POOL = Web3Pool()
