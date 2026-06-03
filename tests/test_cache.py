# SPDX-License-Identifier: LicenseRef-Blockscout
from collections.abc import Callable
from unittest.mock import patch

import anyio
import pytest

from blockscout_mcp_server.cache import CachedContract, ChainsListCache, ContractCache, ProApiConfigCache
from blockscout_mcp_server.config import config

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def fake_monotonic_factory(value: float) -> Callable[[], float]:
    def _fake() -> float:
        return value

    return _fake


@pytest.mark.asyncio
async def test_contract_cache_set_and_get():
    cache = ContractCache()
    contract = CachedContract(metadata={"name": "A"}, source_files={"A.sol": "code"})
    await cache.set("1:addr", contract)
    assert await cache.get("1:addr") == contract


@pytest.mark.asyncio
async def test_contract_cache_lru_eviction():
    cache = ContractCache()
    cache._max_size = 2
    await cache.set("a", CachedContract(metadata={}, source_files={}))
    await cache.set("b", CachedContract(metadata={}, source_files={}))
    await cache.set("c", CachedContract(metadata={}, source_files={}))
    assert await cache.get("a") is None
    assert await cache.get("b") is not None
    assert await cache.get("c") is not None


@pytest.mark.asyncio
async def test_contract_cache_ttl_expiration():
    cache = ContractCache()
    cache._ttl = 0.1
    await cache.set("a", CachedContract(metadata={}, source_files={}))
    await anyio.sleep(0.2)
    assert await cache.get("a") is None


@pytest.mark.asyncio
async def test_contract_cache_get_non_existent():
    cache = ContractCache()
    assert await cache.get("missing") is None


@pytest.mark.asyncio
async def test_contract_cache_access_refreshes_lru():
    cache = ContractCache()
    cache._max_size = 2
    await cache.set("A", CachedContract(metadata={}, source_files={}))
    await cache.set("B", CachedContract(metadata={}, source_files={}))
    assert await cache.get("A") is not None
    await cache.set("C", CachedContract(metadata={}, source_files={}))
    assert await cache.get("B") is None
    assert await cache.get("A") is not None
    assert await cache.get("C") is not None


def test_pro_api_config_cache_empty():
    cache = ProApiConfigCache()
    assert cache.get_if_fresh() is None


def test_pro_api_config_cache_store_and_get():
    cache = ProApiConfigCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(100)):
        cache.store_snapshot({"1": "https://eth"})
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(101)):
        assert cache.get_if_fresh() == {"1": "https://eth"}


def test_pro_api_config_cache_expiry():
    cache = ProApiConfigCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(100)):
        cache.store_snapshot({"1": "https://eth"})
    with patch(
        "blockscout_mcp_server.cache.time.monotonic",
        fake_monotonic_factory(100 + config.pro_api_config_ttl_seconds + 1),
    ):
        assert cache.get_if_fresh() is None


def test_chains_list_cache_invalidate_clears_snapshot():
    c = ChainsListCache()
    c.chains_snapshot = []
    c.expiry_timestamp = 123
    c.invalidate()
    assert c.chains_snapshot is None and c.expiry_timestamp == 0.0


def test_pro_api_config_cache_cooldown_methods():
    cache = ProApiConfigCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(100)):
        cache.mark_refresh_failure()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(101)):
        assert cache.can_retry_refresh() is False
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(200)):
        assert cache.can_retry_refresh() is True


def test_pro_api_config_cache_invalidate_clears_snapshot_and_cooldown():
    cache = ProApiConfigCache()
    cache.chain_urls_snapshot = {"1": "https://eth"}
    cache.expiry_timestamp = 123.0
    cache.refresh_retry_after = 456.0
    cache.invalidate()
    assert cache.chain_urls_snapshot is None
    assert cache.expiry_timestamp == 0.0
    assert cache.refresh_retry_after == 0.0
