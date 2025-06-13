# tests/conftest.py
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_ctx():
    """Provides a mock MCP Context object for tests."""
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    ctx.info = AsyncMock()
    return ctx
