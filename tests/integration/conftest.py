# SPDX-License-Identifier: LicenseRef-Blockscout
"""Integration test setup.

Convention: integration tests use stable, deep-historical data on chain_id=1
(Ethereum mainnet) so assertions are not subject to live-data drift.
Exceptions that deliberately depend on recent activity are documented in the
module docstrings of the affected test files.
"""

import pytest

from blockscout_mcp_server.config import config

def pytest_collection_modifyitems(items):
    """Disable pytest-timeout for integration tests.

    Integration tests make real network calls that legitimately take 30-120s.
    The subprocess runner (scripts/run_integration_tests.py) enforces its own
    per-test wall-clock timeout instead.
    """
    for item in items:
        item.add_marker(pytest.mark.timeout(0))


@pytest.fixture(autouse=True)
def reduce_internal_retries(monkeypatch):
    monkeypatch.setattr(config, "bs_request_max_retries", 1)
