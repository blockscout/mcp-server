"""Tests for the REST API routes."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
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
async def test_list_tools_success(client: AsyncClient, test_mcp_instance: FastMCP):
    """Verify that the /v1/tools endpoint returns a list of tools."""
    test_mcp_instance.list_tools = AsyncMock(return_value=[])
    response = await client.get("/v1/tools")
    assert response.status_code == 200
    assert response.json() == []
    test_mcp_instance.list_tools.assert_called_once()


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_latest_block", new_callable=AsyncMock)
async def test_get_latest_block_success(mock_tool, client: AsyncClient):
    """Test the happy path for a simple REST endpoint."""
    mock_tool.return_value = ToolResponse(data={"block_number": 123})
    response = await client.get("/v1/get_latest_block?chain_id=1")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 123}
    mock_tool.assert_called_once_with(chain_id="1", ctx=ANY)


@pytest.mark.asyncio
async def test_get_latest_block_missing_param(client: AsyncClient):
    """Test that a 400 is returned if a required parameter is missing."""
    response = await client.get("/v1/get_latest_block")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_info", new_callable=AsyncMock)
async def test_get_block_info_with_optional_param(mock_tool, client: AsyncClient):
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


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_info", new_callable=AsyncMock)
async def test_get_block_info_success(mock_tool, client: AsyncClient):
    """Test get_block_info with only required params."""
    mock_tool.return_value = ToolResponse(data={"block_number": 789})
    response = await client.get("/v1/get_block_info?chain_id=1&number_or_hash=123")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 789}
    mock_tool.assert_called_once_with(chain_id="1", number_or_hash="123", ctx=ANY)


@pytest.mark.asyncio
async def test_get_block_info_missing_param(client: AsyncClient):
    """Missing number_or_hash parameter results in error."""
    response = await client.get("/v1/get_block_info?chain_id=1")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'number_or_hash'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.__unlock_blockchain_analysis__", new_callable=AsyncMock)
async def test_get_instructions_success(mock_tool, client: AsyncClient):
    """Test the /get_instructions endpoint."""
    mock_tool.return_value = ToolResponse(data={"msg": "hi"})
    response = await client.get("/v1/get_instructions")
    assert response.status_code == 200
    assert response.json()["data"] == {"msg": "hi"}
    mock_tool.assert_called_once_with(ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.__unlock_blockchain_analysis__", new_callable=AsyncMock)
async def test_unlock_blockchain_analysis_success(mock_tool, client: AsyncClient):
    """Test the /unlock_blockchain_analysis endpoint."""
    mock_tool.return_value = ToolResponse(data={"msg": "unlocked"})
    response = await client.get("/v1/unlock_blockchain_analysis")
    assert response.status_code == 200
    assert response.json()["data"] == {"msg": "unlocked"}
    mock_tool.assert_called_once_with(ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_address_by_ens_name", new_callable=AsyncMock)
async def test_get_address_by_ens_name_success(mock_tool, client: AsyncClient):
    """Test the /get_address_by_ens_name endpoint."""
    mock_tool.return_value = ToolResponse(data={"address": "0xabc"})
    response = await client.get("/v1/get_address_by_ens_name?name=test.eth")
    assert response.status_code == 200
    assert response.json()["data"] == {"address": "0xabc"}
    mock_tool.assert_called_once_with(name="test.eth", ctx=ANY)


@pytest.mark.asyncio
async def test_get_address_by_ens_name_missing_param(client: AsyncClient):
    """Test missing parameter handling for /get_address_by_ens_name."""
    response = await client.get("/v1/get_address_by_ens_name")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'name'"}


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.api.routes.get_transactions_by_address",
    new_callable=AsyncMock,
)
async def test_get_transactions_by_address_success(mock_tool, client: AsyncClient):
    """Test the /get_transactions_by_address endpoint."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    url = "/v1/get_transactions_by_address?chain_id=1&address=0xabc&cursor=foo"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": []}
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        cursor="foo",
        ctx=ANY,
    )


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.api.routes.get_transactions_by_address",
    new_callable=AsyncMock,
)
async def test_get_transactions_by_address_no_cursor(mock_tool, client: AsyncClient):
    """Endpoint works with required params only."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    url = "/v1/get_transactions_by_address?chain_id=1&address=0xabc"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": []}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_transactions_by_address_missing_param(client: AsyncClient):
    """Missing chain_id returns an error."""
    response = await client.get("/v1/get_transactions_by_address?address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.api.routes.get_token_transfers_by_address",
    new_callable=AsyncMock,
)
async def test_get_token_transfers_by_address_success(mock_tool, client: AsyncClient):
    """Test /get_token_transfers_by_address endpoint."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    url = "/v1/get_token_transfers_by_address?chain_id=1&address=0xabc&cursor=foo"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": []}
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        cursor="foo",
        ctx=ANY,
    )


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.api.routes.get_token_transfers_by_address",
    new_callable=AsyncMock,
)
async def test_get_token_transfers_by_address_no_cursor(mock_tool, client: AsyncClient):
    """Endpoint works with required params only."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    url = "/v1/get_token_transfers_by_address?chain_id=1&address=0xabc"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": []}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_missing_param(client: AsyncClient):
    """Missing chain_id parameter."""
    response = await client.get("/v1/get_token_transfers_by_address?address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.lookup_token_by_symbol", new_callable=AsyncMock)
async def test_lookup_token_by_symbol_success(mock_tool, client: AsyncClient):
    """Test /lookup_token_by_symbol endpoint."""
    mock_tool.return_value = ToolResponse(data={"address": "0xdef"})
    response = await client.get("/v1/lookup_token_by_symbol?chain_id=1&symbol=ABC")
    assert response.status_code == 200
    assert response.json()["data"] == {"address": "0xdef"}
    mock_tool.assert_called_once_with(chain_id="1", symbol="ABC", ctx=ANY)


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_missing_param(client: AsyncClient):
    """Missing chain_id results in error."""
    response = await client.get("/v1/lookup_token_by_symbol?symbol=ABC")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_contract_abi", new_callable=AsyncMock)
async def test_get_contract_abi_success(mock_tool, client: AsyncClient):
    """Test /get_contract_abi endpoint."""
    mock_tool.return_value = ToolResponse(data={"abi": []})
    response = await client.get("/v1/get_contract_abi?chain_id=1&address=0xabc")
    assert response.status_code == 200
    assert response.json()["data"] == {"abi": []}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_contract_abi_missing_param(client: AsyncClient):
    """Missing chain_id."""
    response = await client.get("/v1/get_contract_abi?address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.read_contract", new_callable=AsyncMock)
async def test_read_contract_success(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"result": 1})
    url = "/v1/read_contract?chain_id=1&address=0xabc&abi=%7B%7D&function_name=foo"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"result": 1}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", abi={}, function_name="foo", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.read_contract", new_callable=AsyncMock)
async def test_read_contract_with_optional(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"result": 2})
    url = "/v1/read_contract?chain_id=1&address=0xabc&abi=%7B%7D&function_name=foo&args=%5B1%5D&block=5"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"result": 2}
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        abi={},
        function_name="foo",
        args=[1],
        block=5,
        ctx=ANY,
    )


@pytest.mark.asyncio
async def test_read_contract_missing_param(client: AsyncClient):
    response = await client.get("/v1/read_contract?chain_id=1&address=0xabc&function_name=foo")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'abi'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_address_info", new_callable=AsyncMock)
async def test_get_address_info_success(mock_tool, client: AsyncClient):
    """Test /get_address_info endpoint."""
    mock_tool.return_value = ToolResponse(data={"balance": "0"})
    response = await client.get("/v1/get_address_info?chain_id=1&address=0xabc")
    assert response.status_code == 200
    assert response.json()["data"] == {"balance": "0"}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_address_info_missing_param(client: AsyncClient):
    """Missing chain_id parameter."""
    response = await client.get("/v1/get_address_info?address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_tokens_by_address", new_callable=AsyncMock)
async def test_get_tokens_by_address_success(mock_tool, client: AsyncClient):
    """Test /get_tokens_by_address endpoint."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/get_tokens_by_address?chain_id=1&address=0xabc&cursor=foo")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", cursor="foo", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_tokens_by_address", new_callable=AsyncMock)
async def test_get_tokens_by_address_no_cursor(mock_tool, client: AsyncClient):
    """Endpoint works without optional cursor."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/get_tokens_by_address?chain_id=1&address=0xabc")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_tokens_by_address_missing_param(client: AsyncClient):
    """Missing chain_id returns error."""
    response = await client.get("/v1/get_tokens_by_address?address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.transaction_summary", new_callable=AsyncMock)
async def test_transaction_summary_success(mock_tool, client: AsyncClient):
    """Test /transaction_summary endpoint."""
    mock_tool.return_value = ToolResponse(data={"summary": {}})
    response = await client.get("/v1/transaction_summary?chain_id=1&transaction_hash=0x123")
    assert response.status_code == 200
    assert response.json()["data"] == {"summary": {}}
    mock_tool.assert_called_once_with(chain_id="1", transaction_hash="0x123", ctx=ANY)


@pytest.mark.asyncio
async def test_transaction_summary_missing_param(client: AsyncClient):
    """Missing chain_id."""
    response = await client.get("/v1/transaction_summary?transaction_hash=0x123")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.nft_tokens_by_address", new_callable=AsyncMock)
async def test_nft_tokens_by_address_success(mock_tool, client: AsyncClient):
    """Test /nft_tokens_by_address endpoint."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/nft_tokens_by_address?chain_id=1&address=0xabc&cursor=foo")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", cursor="foo", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.nft_tokens_by_address", new_callable=AsyncMock)
async def test_nft_tokens_by_address_no_cursor(mock_tool, client: AsyncClient):
    """Endpoint works without optional cursor."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/nft_tokens_by_address?chain_id=1&address=0xabc")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_nft_tokens_by_address_missing_param(client: AsyncClient):
    """Missing chain_id."""
    response = await client.get("/v1/nft_tokens_by_address?address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_transaction_info", new_callable=AsyncMock)
async def test_get_transaction_info_success(mock_tool, client: AsyncClient):
    """Test /get_transaction_info endpoint."""
    mock_tool.return_value = ToolResponse(data={"hash": "0x123"})
    url = "/v1/get_transaction_info?chain_id=1&transaction_hash=0x123&include_raw_input=true"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"hash": "0x123"}
    mock_tool.assert_called_once_with(
        chain_id="1",
        transaction_hash="0x123",
        include_raw_input=True,
        ctx=ANY,
    )


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_transaction_info", new_callable=AsyncMock)
async def test_get_transaction_info_no_optional(mock_tool, client: AsyncClient):
    """Works without include_raw_input parameter."""
    mock_tool.return_value = ToolResponse(data={"hash": "0xabc"})
    response = await client.get("/v1/get_transaction_info?chain_id=1&transaction_hash=0xabc")
    assert response.status_code == 200
    assert response.json()["data"] == {"hash": "0xabc"}
    mock_tool.assert_called_once_with(chain_id="1", transaction_hash="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_transaction_info_missing_param(client: AsyncClient):
    """Missing chain_id."""
    response = await client.get("/v1/get_transaction_info?transaction_hash=0x123")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_transaction_logs", new_callable=AsyncMock)
async def test_get_transaction_logs_success(mock_tool, client: AsyncClient):
    """Test /get_transaction_logs endpoint."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/get_transaction_logs?chain_id=1&transaction_hash=0x123&cursor=foo")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(chain_id="1", transaction_hash="0x123", cursor="foo", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_transaction_logs", new_callable=AsyncMock)
async def test_get_transaction_logs_no_cursor(mock_tool, client: AsyncClient):
    """Works without optional cursor."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/get_transaction_logs?chain_id=1&transaction_hash=0x123")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(chain_id="1", transaction_hash="0x123", ctx=ANY)


@pytest.mark.asyncio
async def test_get_transaction_logs_missing_param(client: AsyncClient):
    """Missing chain_id."""
    response = await client.get("/v1/get_transaction_logs?transaction_hash=0x123")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "/v1/get_address_logs",
        "/v1/get_address_logs?chain_id=1&address=0xabc",
    ],
)
async def test_get_address_logs_returns_deprecation_notice(client: AsyncClient, url: str):
    """Deprecated /get_address_logs always returns a static 410 response."""
    response = await client.get(url)
    assert response.status_code == 410
    json_response = response.json()
    assert json_response["data"] == {"status": "deprecated"}
    assert "This endpoint is deprecated" in json_response["notes"][0]


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_chains_list", new_callable=AsyncMock)
async def test_get_chains_list_success(mock_tool, client: AsyncClient):
    """Test /get_chains_list endpoint."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/get_chains_list")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(ctx=ANY)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect, status",
    [
        (
            httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            ),
            404,
        ),
        (httpx.TimeoutException("timeout"), 504),
        (ValueError("bad input"), 400),
    ],
)
@patch("blockscout_mcp_server.api.routes.get_latest_block", new_callable=AsyncMock)
async def test_error_handling(mock_tool, client: AsyncClient, side_effect, status):
    """Generic error handling for the REST API."""
    mock_tool.side_effect = side_effect
    response = await client.get("/v1/get_latest_block?chain_id=1")
    assert response.status_code == status
    assert response.json() == {"error": str(side_effect)}
    mock_tool.assert_called_once_with(chain_id="1", ctx=ANY)
