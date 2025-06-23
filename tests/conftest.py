# tests/conftest.py
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_ctx():
    """Provides a mock MCP Context object for tests."""
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    ctx.info = AsyncMock()
    return ctx
