# SPDX-License-Identifier: LicenseRef-Blockscout
"""Integration test setup.

Convention: integration tests use stable, deep-historical data on chain_id=1
(Ethereum mainnet) so assertions are not subject to live-data drift.
Exceptions that deliberately depend on recent activity are documented in the
module docstrings of the affected test files.
"""

import pytest

from blockscout_mcp_server.config import config


@pytest.fixture(autouse=True)
def reduce_internal_retries(monkeypatch):
    monkeypatch.setattr(config, "bs_request_max_retries", 1)
