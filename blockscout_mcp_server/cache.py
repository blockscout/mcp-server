# SPDX-License-Identifier: LicenseRef-Blockscout
"""Simple in-memory cache for chain metadata."""

import time
from collections import OrderedDict

import anyio
from pydantic import BaseModel, Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ChainInfo


class ChainsListCache:
    """In-process TTL cache for the chains list."""

    def __init__(self) -> None:
        self.chains_snapshot: list[ChainInfo] | None = None
        self.expiry_timestamp: float = 0.0
        self.lock = anyio.Lock()

    def invalidate(self) -> None:
        self.chains_snapshot = None
        self.expiry_timestamp = 0.0

    def get_if_fresh(self) -> list[ChainInfo] | None:
        """Return cached chains if the snapshot is still fresh."""
        if self.chains_snapshot is None or time.monotonic() >= self.expiry_timestamp:
            return None
        return self.chains_snapshot

    def needs_refresh(self) -> bool:
        """Return ``True`` if the snapshot is missing or expired."""
        return self.get_if_fresh() is None

    def store_snapshot(self, chains: list[ChainInfo]) -> None:
        """Store a fresh snapshot and compute its expiry timestamp."""
        self.chains_snapshot = chains
        self.expiry_timestamp = time.monotonic() + config.chains_list_ttl_seconds


class ProApiConfigCache:
    """In-process TTL cache for PRO API chain URL mappings."""

    def __init__(self) -> None:
        self.chain_urls_snapshot: dict[str, str] | None = None
        self.expiry_timestamp: float = 0.0
        self.lock = anyio.Lock()
        self.refresh_retry_after: float = 0.0

    def invalidate(self) -> None:
        self.chain_urls_snapshot = None
        self.expiry_timestamp = 0.0
        self.refresh_retry_after = 0.0

    def get_if_fresh(self) -> dict[str, str] | None:
        if self.chain_urls_snapshot is None or time.monotonic() >= self.expiry_timestamp:
            return None
        return self.chain_urls_snapshot

    def can_retry_refresh(self) -> bool:
        return time.monotonic() >= self.refresh_retry_after

    def mark_refresh_failure(self) -> None:
        self.refresh_retry_after = time.monotonic() + config.pro_api_config_refresh_retry_seconds

    def store_snapshot(self, chain_urls: dict[str, str]) -> None:
        self.chain_urls_snapshot = chain_urls
        self.expiry_timestamp = time.monotonic() + config.pro_api_config_ttl_seconds
        self.refresh_retry_after = 0.0


class CachedContract(BaseModel):
    """Represents the pre-processed and cached data for a smart contract."""

    metadata: dict = Field(description="The processed metadata of the contract, with large fields removed.")
    source_files: dict[str, str] = Field(description="A map of file paths to their source code content.")


class ContractCache:
    """In-process, thread-safe, LRU, TTL cache for processed contract data."""

    def __init__(self) -> None:
        self._cache: OrderedDict[str, tuple[CachedContract, float]] = OrderedDict()
        self._lock = anyio.Lock()
        self._max_size = config.contracts_cache_max_number
        self._ttl = config.contracts_cache_ttl_seconds

    async def get(self, key: str) -> CachedContract | None:
        """Retrieve an entry from the cache if it exists and is fresh."""
        async with self._lock:
            if key not in self._cache:
                return None
            contract_data, expiry_timestamp = self._cache[key]
            if time.monotonic() >= expiry_timestamp:
                self._cache.pop(key)
                return None
            self._cache.move_to_end(key)
            return contract_data

    async def set(self, key: str, value: CachedContract) -> None:
        """Add an entry to the cache, enforcing size and TTL."""
        async with self._lock:
            expiry_timestamp = time.monotonic() + self._ttl
            self._cache[key] = (value, expiry_timestamp)
            self._cache.move_to_end(key)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)


# Global singleton instance for the contract cache
contract_cache = ContractCache()
