# SPDX-License-Identifier: LicenseRef-Blockscout
"""Shared pytest fixtures for API route tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.api.routes import register_api_routes


@pytest.fixture
def test_mcp_instance():
    """Provides a FastMCP instance for testing."""
    return FastMCP(name="test-server-for-routes")


@pytest.fixture
def client(test_mcp_instance):
    """Provides an httpx client configured to talk to the test MCP instance."""
    register_api_routes(test_mcp_instance)
    asgi_app = test_mcp_instance.streamable_http_app()
    return AsyncClient(transport=ASGITransport(app=asgi_app), base_url="http://test")
