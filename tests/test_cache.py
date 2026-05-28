# SPDX-License-Identifier: LicenseRef-Blockscout
from collections.abc import Callable
from unittest.mock import patch

import anyio
import pytest

from blockscout_mcp_server.cache import CachedContract, ChainCache, ChainsListCache, ContractCache, ProApiConfigCache
from blockscout_mcp_server.config import config

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def fake_monotonic_factory(value: float) -> Callable[[], float]:
    def _fake() -> float:
        return value

    return _fake


async def test_chain_cache_basic_flow():
    cache = ChainCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(1000)):
        await cache.set("1", "https://a")
    assert cache.get("1") == ("https://a", 1000 + config.chain_cache_ttl_seconds)


async def test_chain_cache_set_failure():
    cache = ChainCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(2000)):
        await cache.set_failure("2")
    assert cache.get("2") == (None, 2000 + config.pro_api_config_ttl_seconds)


async def test_chain_cache_bulk_set():
    cache = ChainCache()
    chain_urls = {"1": "https://a", "2": "https://b"}
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(3000)):
        await cache.bulk_set(chain_urls)
    assert cache.get("1") == ("https://a", 3000 + config.chain_cache_ttl_seconds)
    assert cache.get("2") == ("https://b", 3000 + config.chain_cache_ttl_seconds)


async def test_chain_cache_bulk_set_handles_none():
    cache = ChainCache()
    chain_urls = {"1": "https://a", "2": None}
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(3500)):
        await cache.bulk_set(chain_urls)
    assert cache.get("1") == ("https://a", 3500 + config.chain_cache_ttl_seconds)
    assert cache.get("2") == (None, 3500 + config.chain_cache_ttl_seconds)


async def test_chain_cache_invalidate():
    cache = ChainCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(4000)):
        await cache.set("1", "https://a")
    assert cache.get("1") == ("https://a", 4000 + config.chain_cache_ttl_seconds)
    await cache.invalidate("1")
    await cache.invalidate("1")
    assert cache.get("1") is None


async def test_chain_cache_invalidate_missing_chain_does_not_create_lock():
    cache = ChainCache()
    await cache.invalidate("1")
    assert "1" not in cache._lock_keys


async def test_chain_cache_creates_distinct_locks():
    cache = ChainCache()
    await cache.set("1", "https://a")
    await cache.set("2", "https://b")
    assert {"1", "2"} <= cache._lock_keys
    lock1 = await cache._get_or_create_lock("1")
    lock2 = await cache._get_or_create_lock("2")
    assert lock1 is not lock2


async def test_chain_cache_bulk_set_allows_progress_for_unlocked_chains():
    cache = ChainCache()
    lock1 = await cache._get_or_create_lock("1")
    await lock1.acquire()

    async def run_bulk() -> None:
        await cache.bulk_set({"1": "https://a", "2": "https://b"})

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_bulk)
        for _ in range(50):
            if cache.get("2") is not None:
                break
            await anyio.sleep(0)
        assert cache.get("2")[0] == "https://b"
        lock1.release()

    assert cache.get("1")[0] == "https://a"


async def test_chain_cache_same_chain_uses_same_lock():
    cache = ChainCache()
    lock1 = await cache._get_or_create_lock("1")
    lock2 = await cache._get_or_create_lock("1")
    assert lock1 is lock2


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


async def test_chain_cache_failure_ttl_shorter_than_success():
    cache = ChainCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(1000)):
        await cache.set("1", "https://a")
        await cache.set_failure("2")
    assert cache.get("1")[1] > cache.get("2")[1]


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


async def test_chain_cache_replace_success_entries_removes_missing_and_updates():
    cache = ChainCache()
    with patch("blockscout_mcp_server.cache.time.monotonic", fake_monotonic_factory(1000)):
        await cache.set("1", "https://old")
        await cache.set("2", "https://keep")
        await cache.set_failure("neg")
        await cache.replace_success_entries({"2": "https://new"})
    assert cache.get("1") is None
    assert cache.get("2")[0] == "https://new"
    assert cache.get("neg")[0] is None


def test_pro_api_config_cache_invalidate_clears_snapshot_and_cooldown():
    cache = ProApiConfigCache()
    cache.chain_urls_snapshot = {"1": "https://eth"}
    cache.expiry_timestamp = 123.0
    cache.refresh_retry_after = 456.0
    cache.invalidate()
    assert cache.chain_urls_snapshot is None
    assert cache.expiry_timestamp == 0.0
    assert cache.refresh_retry_after == 0.0
