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
"""

from __future__ import annotations

from itertools import count
from typing import Any

import aiohttp
from web3 import AsyncWeb3
from web3.providers.rpc import AsyncHTTPProvider

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SERVER_VERSION
from blockscout_mcp_server.tools.common import get_blockscout_base_url

DEFAULT_HEADERS = {
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
        """
        headers = dict(self._request_kwargs.get("headers", {}))
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")
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
    """Manage pooled ``AsyncWeb3`` instances with shared sessions.

    Each unique combination of chain and headers gets its own ``AsyncWeb3``
    instance backed by a shared ``aiohttp.ClientSession``. Reusing these
    connections avoids the overhead of establishing new TCP handshakes for
    every contract call.
    """

    def __init__(self) -> None:
        self._pool: dict[tuple[str, tuple[tuple[str, str], ...]], AsyncWeb3] = {}
        self._sessions: dict[tuple[str, tuple[tuple[str, str], ...]], aiohttp.ClientSession] = {}

    async def get(self, chain_id: str, headers: dict[str, str] | None = None) -> AsyncWeb3:
        combined_headers = dict(DEFAULT_HEADERS)
        if headers:
            combined_headers.update(headers)
        hdr_items = tuple(sorted(combined_headers.items()))
        key = (chain_id, hdr_items)
        if key in self._pool:
            return self._pool[key]

        base_url = await get_blockscout_base_url(chain_id)
        endpoint = f"{base_url}/api/eth-rpc"

        provider = AsyncHTTPProviderBlockscout(
            endpoint_uri=endpoint,
            request_kwargs={
                "headers": dict(hdr_items),
                "timeout": config.rpc_request_timeout,
            },
        )
        w3 = AsyncWeb3(provider)

        session = aiohttp.ClientSession(
            # The connector speaks to a single host so ``limit`` matches ``limit_per_host``.
            connector=aiohttp.TCPConnector(
                limit=config.rpc_pool_per_host,
                limit_per_host=config.rpc_pool_per_host,
            )
        )
        provider.set_pooled_session(session)

        self._pool[key] = w3
        self._sessions[key] = session
        return w3

    async def close(self) -> None:
        for w3 in list(self._pool.values()):
            try:
                await w3.provider.disconnect()
            except Exception:
                pass
        for sess in list(self._sessions.values()):
            if not sess.closed:
                try:
                    await sess.close()
                except Exception:
                    pass
        self._pool.clear()
        self._sessions.clear()


WEB3_POOL = Web3Pool()
