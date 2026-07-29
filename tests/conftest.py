# SPDX-License-Identifier: LicenseRef-Blockscout
# tests/conftest.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from blockscout_mcp_server import analytics


@pytest.fixture
def mock_ctx():
    """Provides a mock MCP Context object for tests."""
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    ctx.info = AsyncMock()
    return ctx


@pytest.fixture
def reset_analytics_state(monkeypatch):
    """Reset the analytics module's private state around a test.

    Shared by the analytics test modules, which opt in module-wide via
    ``pytestmark = pytest.mark.usefixtures("reset_analytics_state")``. Deliberately
    not autouse: unrelated test modules must not have analytics state silently
    reset under them. The memoized Mixpanel client is cleared via ``monkeypatch``
    (whose teardown restores the pre-test value); the HTTP-mode flag is reset
    directly on both sides of the test.
    """
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)  # type: ignore[attr-defined]
    yield
    analytics.set_http_mode(False)
