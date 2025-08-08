"""Async Web3 connection pool optimized for Blockscout RPC."""

from __future__ import annotations

from itertools import count
from typing import Any

import aiohttp
from web3 import AsyncWeb3
from web3.providers.rpc import AsyncHTTPProvider

from blockscout_mcp_server.tools.common import get_blockscout_base_url

DEFAULT_HEADERS = {"User-Agent": "Blockscout MCP/0.1"}
REQUEST_TIMEOUT_SECONDS = 60
POOL_TOTAL_CONN = 200
POOL_PER_HOST = 50


class AsyncHTTPProviderBlockscout(AsyncHTTPProvider):
    """Custom provider with Blockscout-specific adaptations."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.request_counter = count(1)
        self.pooled_session: aiohttp.ClientSession | None = None

    def set_pooled_session(self, session: aiohttp.ClientSession) -> None:
        self.pooled_session = session

    async def _make_http_request(self, session: aiohttp.ClientSession, rpc_dict: dict[str, Any]) -> dict[str, Any]:
        async with session.post(
            self.endpoint_uri,
            json=rpc_dict,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def make_request(self, method: str, params: Any) -> dict[str, Any]:  # type: ignore[override]
        if not isinstance(params, list):
            if hasattr(params, "__iter__") and not isinstance(params, str | bytes | dict):
                params = list(params)
            else:
                params = [params] if params is not None else []

        rpc_dict = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": next(self.request_counter),
        }

        if self.pooled_session and not self.pooled_session.closed:
            return await self._make_http_request(self.pooled_session, rpc_dict)

        async with aiohttp.ClientSession() as session:
            return await self._make_http_request(session, rpc_dict)


class Web3Pool:
    """Manage pooled AsyncWeb3 instances with shared sessions."""

    def __init__(self) -> None:
        self._pool: dict[tuple[str, tuple[tuple[str, str], ...]], AsyncWeb3] = {}
        self._sessions: dict[tuple[str, tuple[tuple[str, str], ...]], aiohttp.ClientSession] = {}

    async def get(self, chain_id: str, headers: dict[str, str] | None = None) -> AsyncWeb3:
        hdr_items = tuple(sorted((headers or DEFAULT_HEADERS).items()))
        key = (chain_id, hdr_items)
        if key in self._pool:
            return self._pool[key]

        base_url = await get_blockscout_base_url(chain_id)
        endpoint = f"{base_url}/api/eth-rpc"

        provider = AsyncHTTPProviderBlockscout(
            endpoint_uri=endpoint,
            request_kwargs={"headers": dict(hdr_items), "timeout": REQUEST_TIMEOUT_SECONDS},
        )
        w3 = AsyncWeb3(provider)

        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=POOL_TOTAL_CONN, limit_per_host=POOL_PER_HOST)
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
