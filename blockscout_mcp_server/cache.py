import time
from typing import Any

from blockscout_mcp_server.config import config


def find_blockscout_url(chain_data: dict) -> str | None:
    """Iterates through explorers to find the one hosted by Blockscout."""
    for explorer in chain_data.get("explorers", []):
        if isinstance(explorer, dict) and explorer.get("hostedBy") == "blockscout":
            url = explorer.get("url")
            if url:
                return url.rstrip("/")
    return None


class ChainCache:
    def __init__(self) -> None:
        # Cache: chain_id -> (blockscout_url_or_none, expiry_timestamp)
        self._cache: dict[str, tuple[str | None, float]] = {}

    def get(self, chain_id: str) -> tuple[str | None, float] | None:
        """Retrieves an entry from the cache."""
        return self._cache.get(chain_id)

    def set(self, chain_id: str, chain_data: dict[str, Any]) -> None:
        """Processes and caches a single chain's data."""
        blockscout_url = find_blockscout_url(chain_data)
        expiry = time.time() + config.chain_cache_ttl_seconds
        self._cache[chain_id] = (blockscout_url, expiry)

    def set_failure(self, chain_id: str) -> None:
        """Caches a failure to find a chain."""
        expiry = time.time() + config.chain_cache_ttl_seconds
        self._cache[chain_id] = (None, expiry)

    def bulk_set(self, chains_data: dict[str, Any]) -> None:
        """Caches the data from a bulk /api/chains response."""
        for chain_id, chain_data in chains_data.items():
            if isinstance(chain_data, dict):
                self.set(chain_id, chain_data)

    def invalidate(self, chain_id: str) -> None:
        """Remove an entry from the cache if present."""
        self._cache.pop(chain_id, None)
