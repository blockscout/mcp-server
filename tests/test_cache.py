from unittest.mock import patch

from blockscout_mcp_server.cache import ChainCache
from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.common import find_blockscout_url


def test_find_blockscout_url_success():
    chain_data = {
        "explorers": [
            {"hostedBy": "blockscout", "url": "https://example.blockscout.com"},
            {"hostedBy": "other", "url": "https://other.com"},
        ]
    }
    assert find_blockscout_url(chain_data) == "https://example.blockscout.com"


def test_find_blockscout_url_no_match():
    chain_data = {"explorers": [{"hostedBy": "other", "url": "https://x"}]}
    assert find_blockscout_url(chain_data) is None


def test_chain_cache_basic_flow():
    cache = ChainCache()
    with patch("time.time", return_value=1000):
        cache.set("1", "https://a")
    assert cache.get("1") == ("https://a", 1000 + config.chain_cache_ttl_seconds)


def test_chain_cache_set_failure():
    cache = ChainCache()
    with patch("time.time", return_value=2000):
        cache.set_failure("2")
    assert cache.get("2") == (None, 2000 + config.chain_cache_ttl_seconds)


def test_chain_cache_bulk_set():
    cache = ChainCache()
    chain_urls = {
        "1": "https://a",
        "2": "https://b",
    }
    with patch("time.time", return_value=3000):
        cache.bulk_set(chain_urls)
    assert cache.get("1") == ("https://a", 3000 + config.chain_cache_ttl_seconds)
    assert cache.get("2") == ("https://b", 3000 + config.chain_cache_ttl_seconds)


def test_chain_cache_invalidate():
    cache = ChainCache()
    with patch("time.time", return_value=4000):
        cache.set("1", "https://a")
    assert cache.get("1") == ("https://a", 4000 + config.chain_cache_ttl_seconds)
    cache.invalidate("1")
    assert cache.get("1") is None
