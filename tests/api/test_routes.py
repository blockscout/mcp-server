"""Tests for the static REST API routes."""

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.api.routes import register_api_routes


@pytest.mark.asyncio
async def test_static_routes_work_correctly():
    """Verify that static routes return correct content and headers after registration."""
    test_mcp = FastMCP(name="test-server-for-routes")
    register_api_routes(test_mcp)
    async with AsyncClient(
        transport=ASGITransport(app=test_mcp.streamable_http_app()),
        base_url="http://testserver",
    ) as client:
        response_health = await client.get("/health")
        assert response_health.status_code == 200
        assert response_health.json() == {"status": "ok"}
        assert "application/json" in response_health.headers["content-type"]

        response_main = await client.get("/")
        assert response_main.status_code == 200
        assert "<h1>Blockscout MCP Server</h1>" in response_main.text
        assert "text/html" in response_main.headers["content-type"]

        response_llms = await client.get("/llms.txt")
        assert response_llms.status_code == 200
        assert "# Blockscout MCP Server" in response_llms.text
        assert "text/plain" in response_llms.headers["content-type"]


@pytest.mark.asyncio
async def test_routes_not_found_on_clean_app():
    """Verify that static routes are not available on a clean, un-configured app."""
    test_mcp = FastMCP(name="test-server-clean")
    async with AsyncClient(
        transport=ASGITransport(app=test_mcp.streamable_http_app()),
        base_url="http://testserver",
    ) as client:
        assert (await client.get("/health")).status_code == 404
        assert (await client.get("/")).status_code == 404
        assert (await client.get("/llms.txt")).status_code == 404
