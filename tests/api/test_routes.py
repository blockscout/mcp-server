"""Tests for the REST API routes."""

from unittest.mock import ANY, AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.api.routes import register_api_routes
from blockscout_mcp_server.models import ToolResponse


@pytest.fixture
def test_mcp_instance():
    """Provides a FastMCP instance for testing."""
    return FastMCP(name="test-server-for-routes")


@pytest.fixture
def client(test_mcp_instance):
    """Provides an httpx client configured to talk to the test MCP instance."""
    register_api_routes(test_mcp_instance)
    asgi_app = test_mcp_instance.streamable_http_app()
    asgi_app.state.mcp_instance = test_mcp_instance
    return AsyncClient(transport=ASGITransport(app=asgi_app), base_url="http://test")


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.INDEX_HTML_CONTENT", "<h1>Blockscout MCP Server</h1>")
@patch("blockscout_mcp_server.api.routes.LLMS_TXT_CONTENT", "# Blockscout MCP Server")
async def test_static_routes_work_correctly(client: AsyncClient):
    """Verify that static routes return correct content and headers after registration."""
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
        base_url="http://test",
    ) as test_client:
        assert (await test_client.get("/health")).status_code == 404
        assert (await test_client.get("/")).status_code == 404
        assert (await test_client.get("/llms.txt")).status_code == 404


@pytest.mark.asyncio
async def test_list_tools_rest(client: AsyncClient, test_mcp_instance: FastMCP):
    """Verify that the /v1/tools endpoint returns a list of tools."""
    test_mcp_instance.list_tools = AsyncMock(return_value=[])
    response = await client.get("/v1/tools")
    assert response.status_code == 200
    assert response.json() == []
    test_mcp_instance.list_tools.assert_called_once()


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_latest_block", new_callable=AsyncMock)
async def test_get_latest_block_rest_success(mock_tool, client: AsyncClient):
    """Test the happy path for a simple REST endpoint."""
    mock_tool.return_value = ToolResponse(data={"block_number": 123})
    response = await client.get("/v1/get_latest_block?chain_id=1")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 123}
    mock_tool.assert_called_once_with(chain_id="1", ctx=ANY)


@pytest.mark.asyncio
async def test_get_latest_block_rest_missing_param(client: AsyncClient):
    """Test that a 400 is returned if a required parameter is missing."""
    response = await client.get("/v1/get_latest_block")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_info", new_callable=AsyncMock)
async def test_get_block_info_rest_with_optional_param(mock_tool, client: AsyncClient):
    """Test an endpoint with both required and optional boolean parameters."""
    mock_tool.return_value = ToolResponse(data={"block_number": 456})
    response = await client.get("/v1/get_block_info?chain_id=1&number_or_hash=latest&include_transactions=true")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 456}
    mock_tool.assert_called_once_with(
        chain_id="1",
        number_or_hash="latest",
        include_transactions=True,
        ctx=ANY,
    )
