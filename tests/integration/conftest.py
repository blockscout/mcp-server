# SPDX-License-Identifier: LicenseRef-Blockscout
import pytest

from blockscout_mcp_server.config import config


@pytest.fixture(autouse=True)
def reduce_internal_retries(monkeypatch):
    monkeypatch.setattr(config, "bs_request_max_retries", 1)
