"""Simple in-memory cache for chain metadata."""

import time

from blockscout_mcp_server.config import config


class ChainCache:
    def __init__(self) -> None:
        # Cache: chain_id -> (blockscout_url_or_none, expiry_timestamp)
        # Note: this simple dict is not thread-safe when multiple threads try
        # to write the same new key concurrently. For the HTTP server in
        # streamable mode we run a single-thread event loop, so the risk is low.
        # TODO: implement a thread-safe cache for official deployments.
        self._cache: dict[str, tuple[str | None, float]] = {}

    def get(self, chain_id: str) -> tuple[str | None, float] | None:
        """Retrieves an entry from the cache."""
        return self._cache.get(chain_id)

    def set(self, chain_id: str, blockscout_url: str | None) -> None:
        """Cache the URL (or lack thereof) for a single chain."""
        expiry = time.time() + config.chain_cache_ttl_seconds
        self._cache[chain_id] = (blockscout_url, expiry)

    def set_failure(self, chain_id: str) -> None:
        """Caches a failure to find a chain."""
        expiry = time.time() + config.chain_cache_ttl_seconds
        self._cache[chain_id] = (None, expiry)

    def bulk_set(self, chain_urls: dict[str, str | None]) -> None:
        """Caches URLs from a bulk /api/chains response."""
        for chain_id, url in chain_urls.items():
            self.set(chain_id, url)

    def invalidate(self, chain_id: str) -> None:
        """Remove an entry from the cache if present."""
        self._cache.pop(chain_id, None)
