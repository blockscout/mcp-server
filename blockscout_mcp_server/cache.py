"""Simple in-memory cache for chain metadata."""

import time

import anyio

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ChainInfo


class ChainCache:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[str | None, float]] = {}
        self._locks_lock = anyio.Lock()
        self._locks: dict[str, anyio.Lock] = {}

    async def _get_or_create_lock(self, chain_id: str) -> anyio.Lock:
        """Get or create a lock for a specific chain."""
        if lock := self._locks.get(chain_id):
            return lock
        async with self._locks_lock:
            if lock := self._locks.get(chain_id):
                return lock
            new_lock = anyio.Lock()
            self._locks[chain_id] = new_lock
            return new_lock

    @property
    def _lock_keys(self) -> set[str]:
        """Return a snapshot of chain IDs with initialized locks."""
        return set(self._locks.keys())

    def get(self, chain_id: str) -> tuple[str | None, float] | None:
        """Retrieve an entry without validating expiry (no locking).

        Returns ``(url_or_none, expiry_monotonic)`` or ``None``.
        """
        return self._cache.get(chain_id)

    async def set(self, chain_id: str, blockscout_url: str | None) -> None:
        """Cache the URL (or lack thereof) for a single chain."""
        expiry = time.monotonic() + config.chain_cache_ttl_seconds
        chain_lock = await self._get_or_create_lock(chain_id)
        async with chain_lock:
            self._cache[chain_id] = (blockscout_url, expiry)

    async def set_failure(self, chain_id: str) -> None:
        """Cache a failure to find a chain."""
        await self.set(chain_id, None)

    async def bulk_set(self, chain_urls: dict[str, str | None]) -> None:
        """Cache URLs from a bulk /api/chains response concurrently."""
        expiry = time.monotonic() + config.chain_cache_ttl_seconds

        async def _set_with_expiry(chain_id: str, url: str | None) -> None:
            chain_lock = await self._get_or_create_lock(chain_id)
            async with chain_lock:
                self._cache[chain_id] = (url, expiry)

        async with anyio.create_task_group() as tg:
            for chain_id, url in chain_urls.items():
                tg.start_soon(_set_with_expiry, chain_id, url)

    async def invalidate(self, chain_id: str) -> None:
        """Remove an entry from the cache if present."""
        if chain_id not in self._cache:
            return
        chain_lock = await self._get_or_create_lock(chain_id)
        async with chain_lock:
            self._cache.pop(chain_id, None)


class ChainsListCache:
    """In-process TTL cache for the chains list."""

    def __init__(self) -> None:
        self.chains_snapshot: list[ChainInfo] | None = None
        self.expiry_timestamp: float = 0.0
        self.lock = anyio.Lock()

    def get_if_fresh(self) -> list[ChainInfo] | None:
        """Return cached chains if the snapshot is still fresh."""
        if self.chains_snapshot is None or time.time() >= self.expiry_timestamp:
            return None
        return self.chains_snapshot

    def needs_refresh(self) -> bool:
        """Return ``True`` if the snapshot is missing or expired."""
        return self.get_if_fresh() is None

    def store_snapshot(self, chains: list[ChainInfo]) -> None:
        """Store a fresh snapshot and compute its expiry timestamp."""
        self.chains_snapshot = chains
        self.expiry_timestamp = time.time() + config.chains_list_ttl_seconds
