# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the REST API routes."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.config import config as bms_config
from blockscout_mcp_server.models import AdvancedFilterItem, TokenTransfer, ToolResponse, TransactionInfoData
from blockscout_mcp_server.tools.common import CreditsExhaustedError


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.track_event")
@patch("blockscout_mcp_server.api.routes.INDEX_HTML_CONTENT", "<h1>Blockscout MCP Server</h1>")
@patch("blockscout_mcp_server.api.routes.LLMS_TXT_CONTENT", "# Blockscout MCP Server")
async def test_static_routes_work_correctly(mock_track_event, client: AsyncClient):
    """Verify that static routes return correct content and headers after registration."""
    response_health = await client.get("/health")
    assert response_health.status_code == 200
    assert response_health.json() == {"status": "ok"}
    assert "application/json" in response_health.headers["content-type"]

    response_main = await client.get("/")
    assert response_main.status_code == 200
    assert "<h1>Blockscout MCP Server</h1>" in response_main.text
    assert "text/html" in response_main.headers["content-type"]
    mock_track_event.assert_called_once_with(ANY, "PageView", {"path": "/"})

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
    mocked_tool = MagicMock()
    mocked_tool.model_dump.return_value = {"name": "tool", "_meta": {"source": "test"}}
    test_mcp_instance.list_tools = AsyncMock(return_value=[mocked_tool])

    response = await client.get("/v1/tools")

    assert response.status_code == 200
    assert response.json() == [{"name": "tool", "_meta": {"source": "test"}}]
    test_mcp_instance.list_tools.assert_called_once()
    mocked_tool.model_dump.assert_called_once_with(mode="json", by_alias=True)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_number", new_callable=AsyncMock)
async def test_get_block_number_success(mock_tool, client: AsyncClient):
    """Test the happy path for a simple REST endpoint."""
    mock_tool.return_value = ToolResponse(data={"block_number": 123})
    response = await client.get("/v1/get_block_number?chain_id=1")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 123}
    mock_tool.assert_called_once_with(chain_id="1", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_number", new_callable=AsyncMock)
async def test_get_block_number_with_datetime_success(mock_tool, client: AsyncClient):
    """Test get_block_number with optional datetime parameter."""
    mock_tool.return_value = ToolResponse(data={"block_number": 456})
    response = await client.get("/v1/get_block_number?chain_id=1&datetime=2023-01-01T00:00:00Z")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 456}
    mock_tool.assert_called_once_with(chain_id="1", datetime="2023-01-01T00:00:00Z", ctx=ANY)


@pytest.mark.asyncio
async def test_get_block_number_missing_param(client: AsyncClient):
    """Test that a 400 is returned if a required parameter is missing."""
    response = await client.get("/v1/get_block_number")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_number", new_callable=AsyncMock)
async def test_get_latest_block_success(mock_tool, client: AsyncClient):
    """Test the legacy endpoint forwards to get_block_number."""
    mock_tool.return_value = ToolResponse(data={"block_number": 123})
    response = await client.get("/v1/get_latest_block?chain_id=1")
    assert response.status_code == 200
    assert response.json()["data"] == {"block_number": 123}
    mock_tool.assert_called_once_with(chain_id="1", datetime=None, ctx=ANY)


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
@patch(
    "blockscout_mcp_server.api.routes.inspect_contract_code",
    new_callable=AsyncMock,
)
async def test_inspect_contract_code_route_success(mock_tool, client: AsyncClient):
    """Test inspect_contract_code in metadata mode."""
    mock_tool.return_value = ToolResponse(data={"name": "TestContract"})
    response = await client.get("/v1/inspect_contract_code?chain_id=1&address=0xabc")
    assert response.status_code == 200
    assert response.json()["data"] == {"name": "TestContract"}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", ctx=ANY)


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.api.routes.inspect_contract_code",
    new_callable=AsyncMock,
)
async def test_inspect_contract_code_route_with_file(mock_tool, client: AsyncClient):
    """Test inspect_contract_code in file mode."""
    mock_tool.return_value = ToolResponse(data={"file_content": "pragma solidity ^0.8.0;"})
    response = await client.get("/v1/inspect_contract_code?chain_id=1&address=0xabc&file_name=Test.sol")
    assert response.status_code == 200
    assert response.json()["data"] == {"file_content": "pragma solidity ^0.8.0;"}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", file_name="Test.sol", ctx=ANY)


@pytest.mark.asyncio
async def test_inspect_contract_code_route_missing_param(client: AsyncClient):
    """Missing required parameter returns 400."""
    response = await client.get("/v1/inspect_contract_code?chain_id=1")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'address'"}


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
    mock_tool.return_value = ToolResponse(data=[AdvancedFilterItem(**{"from": "0xfrom", "to": "0xto"})])
    url = "/v1/get_transactions_by_address?chain_id=1&address=0xabc&age_from=2025-01-01T00:00:00.00Z&cursor=foo"
    response = await client.get(url)
    assert response.status_code == 200
    transfer_item = response.json()["data"][0]
    assert transfer_item["from"] == "0xfrom"
    assert transfer_item["to"] == "0xto"
    assert "from_address" not in transfer_item
    assert "to_address" not in transfer_item
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        age_from="2025-01-01T00:00:00.00Z",
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
    mock_tool.return_value = ToolResponse(data=[AdvancedFilterItem(**{"from": "0xfrom", "to": "0xto"})])
    url = "/v1/get_transactions_by_address?chain_id=1&address=0xabc&age_from=2025-01-01T00:00:00.00Z"
    response = await client.get(url)
    assert response.status_code == 200
    transfer_item = response.json()["data"][0]
    assert transfer_item["from"] == "0xfrom"
    assert transfer_item["to"] == "0xto"
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", age_from="2025-01-01T00:00:00.00Z", ctx=ANY)


@pytest.mark.asyncio
async def test_get_transactions_by_address_missing_param(client: AsyncClient):
    """Missing chain_id returns an error."""
    response = await client.get("/v1/get_transactions_by_address?address=0xabc&age_from=2025-01-01T00:00:00.00Z")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
async def test_get_transactions_by_address_missing_age_from(client: AsyncClient):
    """Missing age_from returns an error."""
    response = await client.get("/v1/get_transactions_by_address?chain_id=1&address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'age_from'"}


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.api.routes.get_token_transfers_by_address",
    new_callable=AsyncMock,
)
async def test_get_token_transfers_by_address_success(mock_tool, client: AsyncClient):
    """Test /get_token_transfers_by_address endpoint."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    url = "/v1/get_token_transfers_by_address?chain_id=1&address=0xabc&age_from=2025-01-01T00:00:00.00Z&cursor=foo"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": []}
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        age_from="2025-01-01T00:00:00.00Z",
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
    url = "/v1/get_token_transfers_by_address?chain_id=1&address=0xabc&age_from=2025-01-01T00:00:00.00Z"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"items": []}
    mock_tool.assert_called_once_with(chain_id="1", address="0xabc", age_from="2025-01-01T00:00:00.00Z", ctx=ANY)


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_missing_param(client: AsyncClient):
    """Missing chain_id parameter."""
    response = await client.get("/v1/get_token_transfers_by_address?address=0xabc&age_from=2025-01-01T00:00:00.00Z")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_missing_age_from(client: AsyncClient):
    """Missing age_from parameter."""
    response = await client.get("/v1/get_token_transfers_by_address?chain_id=1&address=0xabc")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'age_from'"}


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
        args="[1]",
        block=5,
        ctx=ANY,
    )


@pytest.mark.asyncio
async def test_read_contract_missing_param(client: AsyncClient):
    response = await client.get("/v1/read_contract?chain_id=1&address=0xabc&function_name=foo")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'abi'"}


@pytest.mark.asyncio
async def test_read_contract_invalid_abi_json(client: AsyncClient):
    url = "/v1/read_contract?chain_id=1&address=0xabc&abi=%7B&function_name=foo"
    resp = await client.get(url)
    assert resp.status_code == 400
    assert "Invalid JSON for 'abi'" in resp.json()["error"]


@pytest.mark.asyncio
async def test_read_contract_invalid_args_json(client: AsyncClient):
    # The tool validation fails and bubbles as 400 via decorator
    url = "/v1/read_contract?chain_id=1&address=0xabc&abi=%7B%7D&function_name=foo&args=%5B"
    resp = await client.get(url)
    assert resp.status_code == 400
    assert "must be a JSON array string" in resp.json()["error"]


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
async def test_transaction_summary_success(client: AsyncClient):
    """Test /transaction_summary endpoint."""
    response = await client.get("/v1/transaction_summary?chain_id=1&transaction_hash=0x123")
    assert response.status_code == 410
    payload = response.json()
    assert payload["data"] == {"status": "deprecated"}
    assert payload["notes"] == [
        "This endpoint is deprecated and will be removed in a future version.",
        (
            "Please use `direct_api_call` with "
            "`endpoint_path='/api/v2/transactions/{transaction_hash}/summary'` to retrieve this data."
        ),
    ]


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
    mock_tool.return_value = ToolResponse(
        data=TransactionInfoData(
            **{
                "from": "0xfrom",
                "to": "0xto",
                "token_transfers": [TokenTransfer(**{"from": "0xa", "to": "0xb", "type": "transfer", "token": {}})],
            },
        )
    )
    url = "/v1/get_transaction_info?chain_id=1&transaction_hash=0x123&include_raw_input=true"
    response = await client.get(url)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["from"] == "0xfrom"
    assert data["to"] == "0xto"
    assert "from_address" not in data
    assert "to_address" not in data
    transfer = data["token_transfers"][0]
    assert transfer["from"] == "0xa"
    assert transfer["to"] == "0xb"
    assert transfer["type"] == "transfer"
    assert "from_address" not in transfer
    assert "to_address" not in transfer
    assert "transfer_type" not in transfer
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
    mock_tool.return_value = ToolResponse(
        data=TransactionInfoData(
            **{
                "from": "0xfrom",
                "to": "0xto",
                "token_transfers": [TokenTransfer(**{"from": "0xa", "to": "0xb", "type": "mint", "token": None})],
            },
        )
    )
    response = await client.get("/v1/get_transaction_info?chain_id=1&transaction_hash=0xabc")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["from"] == "0xfrom"
    assert data["to"] == "0xto"
    assert "from_address" not in data
    assert "to_address" not in data
    transfer = data["token_transfers"][0]
    assert transfer["from"] == "0xa"
    assert transfer["to"] == "0xb"
    assert transfer["type"] == "mint"
    mock_tool.assert_called_once_with(chain_id="1", transaction_hash="0xabc", ctx=ANY)


@pytest.mark.asyncio
async def test_get_transaction_info_missing_param(client: AsyncClient):
    """Missing chain_id."""
    response = await client.get("/v1/get_transaction_info?transaction_hash=0x123")
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
@pytest.mark.parametrize(
    "url",
    [
        "/v1/get_transaction_logs",
        "/v1/get_transaction_logs?chain_id=1&transaction_hash=0xabc",
    ],
)
async def test_get_transaction_logs_returns_deprecation_notice(client: AsyncClient, url: str):
    """Deprecated /get_transaction_logs always returns a static 410 response."""
    response = await client.get(url)
    assert response.status_code == 410
    json_response = response.json()
    assert json_response["data"] == {"status": "deprecated"}
    assert "direct_api_call" in json_response["notes"][1]


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
@patch("blockscout_mcp_server.api.routes.get_chains_list", new_callable=AsyncMock)
async def test_get_chains_list_with_query(mock_tool, client: AsyncClient):
    """Test /get_chains_list endpoint with query."""
    mock_tool.return_value = ToolResponse(data=[])
    response = await client.get("/v1/get_chains_list?query=ethereum")
    assert response.status_code == 200
    assert response.json()["data"] == []
    mock_tool.assert_called_once_with(query="ethereum", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_required_only(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.get("/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats")
    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_tool.assert_called_once_with(chain_id="1", endpoint_path="/api/v2/stats", ctx=ANY)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_success_with_cursor_and_query_params(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"ok": True})
    url = "/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats&query_params[page]=1&cursor=abc"
    response = await client.get(url)
    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_tool.assert_called_once_with(
        chain_id="1",
        endpoint_path="/api/v2/stats",
        query_params={"page": "1"},
        cursor="abc",
        ctx=ANY,
    )


@pytest.mark.asyncio
async def test_direct_api_call_missing_endpoint_path(client: AsyncClient):
    response = await client.get("/v1/direct_api_call?chain_id=1")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'endpoint_path'"}


@pytest.mark.asyncio
async def test_direct_api_call_missing_chain_id(client: AsyncClient):
    response = await client.get("/v1/direct_api_call?endpoint_path=/api/v2/stats")
    assert response.status_code == 400
    assert response.json() == {"error": "Missing required query parameter: 'chain_id'"}


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
        (CreditsExhaustedError("Out of credits"), 402),
    ],
)
@patch("blockscout_mcp_server.api.routes.get_block_number", new_callable=AsyncMock)
async def test_error_handling(mock_tool, client: AsyncClient, side_effect, status):
    """Generic error handling for the REST API."""
    mock_tool.side_effect = side_effect
    response = await client.get("/v1/get_block_number?chain_id=1")
    assert response.status_code == status
    assert response.json() == {"error": str(side_effect)}
    mock_tool.assert_called_once_with(chain_id="1", ctx=ANY)


# ---------------------------------------------------------------------------
# /v1/report_tool_usage — shared payload/POST helper
# ---------------------------------------------------------------------------
# Every report-endpoint test posts the same base payload and User-Agent, varying
# only the auth-signal fields under test; ``post_report`` keeps each test to the
# fields it actually exercises.

_REPORT_USER_AGENT = "BlockscoutMCP/0.0"


async def post_report(client: AsyncClient, **overrides):
    """POST the base /v1/report_tool_usage payload (with *overrides* applied) and the standard User-Agent.

    Keyword *overrides* add or replace top-level payload fields, so a test can set
    ``auth_origin``/``api_key_fingerprint`` (to a value, ``None``, or omit them) without
    restating the shared ``tool_name``/``tool_args``/client fields.
    """
    payload = {
        "tool_name": "dummy",
        "tool_args": {"a": 1},
        "client_name": "cli",
        "client_version": "1.0",
        "protocol_version": "1.1",
    }
    payload.update(overrides)
    return await client.post("/v1/report_tool_usage", json=payload, headers={"User-Agent": _REPORT_USER_AGENT})


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.analytics.track_community_usage")
async def test_report_tool_usage_success(mock_track, client: AsyncClient):
    response = await post_report(client, auth_origin="client", api_key_fingerprint="a" * 64)
    assert response.status_code == 202
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["report"].tool_name == "dummy"
    assert kwargs["report"].tool_args == {"a": 1}
    assert kwargs["report"].client_name == "cli"
    assert kwargs["report"].client_version == "1.0"
    assert kwargs["report"].protocol_version == "1.1"
    assert kwargs["report"].auth_origin == "client"
    assert kwargs["report"].api_key_fingerprint == "a" * 64
    assert kwargs["user_agent"] == _REPORT_USER_AGENT


@pytest.mark.asyncio
async def test_report_tool_usage_bad_body(client: AsyncClient):
    response = await client.post("/v1/report_tool_usage", json={"tool_name": "x"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_tool_usage_missing_header(client: AsyncClient):
    payload = {
        "tool_name": "dummy",
        "tool_args": {},
        "client_name": "cli",
        "client_version": "1.0",
        "protocol_version": "1.1",
    }
    response = await client.post("/v1/report_tool_usage", json=payload, headers={"User-Agent": ""})
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.analytics.track_community_usage")
async def test_report_tool_usage_legacy_payload_without_new_fields(mock_track, client: AsyncClient):
    """A legacy payload that omits auth_origin/api_key_fingerprint is still accepted.

    The analytics layer renders a None auth_origin as 'unknown', so the forwarded report
    must carry None rather than being rejected outright.
    """
    response = await post_report(client)
    assert response.status_code == 202
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["report"].auth_origin is None


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.analytics.track_community_usage")
async def test_report_tool_usage_tolerates_unrecognized_auth_origin(mock_track, client: AsyncClient):
    """An unrecognized auth_origin does not drop the otherwise-valid report.

    The value this receiver does not recognize is coerced to None by the model (rendered as
    "unknown" downstream), so the report is still accepted (202) and forwarded once with
    `auth_origin is None`. This keeps a version-skewed community reporter reporting instead of
    silently losing 100% of its telemetry to a 422 that the fire-and-forget sender never sees.
    """
    response = await post_report(client, auth_origin="bogus")
    assert response.status_code == 202
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["report"].auth_origin is None


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.analytics.track_community_usage")
async def test_report_tool_usage_tolerates_malformed_fingerprint(mock_track, client: AsyncClient):
    """A syntactically invalid api_key_fingerprint does not drop the otherwise-valid report.

    The not-yet-consumed fingerprint is coerced to None by the model, so the report is still
    accepted (202) and forwarded once with `api_key_fingerprint is None`.
    """
    response = await post_report(client, api_key_fingerprint="not-a-hash")
    assert response.status_code == 202
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["report"].api_key_fingerprint is None


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.analytics.track_community_usage")
async def test_report_tool_usage_explicit_none_auth_origin_string_with_null_fingerprint(
    mock_track, client: AsyncClient
):
    """The exact no-key wire shape an updated reporter sends: auth_origin="none" with a null
    fingerprint, sent explicitly rather than omitted.

    This guards against the endpoint rejecting real no-key reports from updated reporters.
    """
    response = await post_report(client, auth_origin="none", api_key_fingerprint=None)
    assert response.status_code == 202
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["report"].auth_origin == "none"
    assert kwargs["report"].api_key_fingerprint is None


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.analytics.track_community_usage")
async def test_report_tool_usage_explicit_null_auth_origin_with_null_fingerprint(mock_track, client: AsyncClient):
    """A JSON null auth_origin (not the string "none") with a null fingerprint is accepted.

    Phase 4 adds both keys to the outbound payload unconditionally, so any caller that omits
    the auth_origin keyword causes the sender to serialize a literal `"auth_origin": null` on
    the wire. This is the HTTP-boundary counterpart of the Phase 1 explicit-auth_origin=None
    model test, and it is the only route case that catches a `Literal[...]`-without-`| None`
    typing regression, which would otherwise 422 a real report.
    """
    response = await post_report(client, auth_origin=None, api_key_fingerprint=None)
    assert response.status_code == 202
    mock_track.assert_called_once()
    _, kwargs = mock_track.call_args
    assert kwargs["report"].auth_origin is None
    assert kwargs["report"].api_key_fingerprint is None


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_post_success(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.post("/v1/direct_api_call?chain_id=1&endpoint_path=/json-rpc", json={"id": 1})
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1", endpoint_path="/json-rpc", method="POST", json_body={"id": 1}, ctx=ANY
    )


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_post_with_query_params(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.post(
        "/v1/direct_api_call?chain_id=1&endpoint_path=/json-rpc&query_params[foo]=bar", json={"id": 1}
    )
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1",
        endpoint_path="/json-rpc",
        method="POST",
        json_body={"id": 1},
        query_params={"foo": "bar"},
        ctx=ANY,
    )


@pytest.mark.asyncio
async def test_direct_api_call_post_missing_body(client: AsyncClient):
    response = await client.post("/v1/direct_api_call?chain_id=1&endpoint_path=/json-rpc")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_direct_api_call_post_invalid_json_body(client: AsyncClient):
    response = await client.post(
        "/v1/direct_api_call?chain_id=1&endpoint_path=/json-rpc",
        content="not-json-at-all",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_reserved_query_keys_not_forwarded(mock_tool, client: AsyncClient):
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.get("/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats&method=POST&json_body=foo")
    assert response.status_code == 200
    mock_tool.assert_called_once_with(chain_id="1", endpoint_path="/api/v2/stats", ctx=ANY)


# ---------------------------------------------------------------------------
# Phase 5: Cross-mode end-to-end — REST mode, credit advisory note
# ---------------------------------------------------------------------------


class _MockBlockResponse:
    """Minimal fake httpx response used inside the REST end-to-end credit test."""

    def __init__(self, json_data, headers=None):
        self._json_data = json_data
        self.status_code = 200
        self.reason_phrase = "OK"
        self.request = httpx.Request("GET", "https://api.blockscout.com/1/x")
        self.text = ""
        self.headers = headers if headers is not None else {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


class _SimpleBlockClient:
    """Async context-manager HTTP client that returns a fixed response."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_rest_mode_low_credits_note_in_response(client: AsyncClient):
    """REST mode: /v1/get_block_number endpoint produces a JSON response whose
    `notes` array contains the low-credits advisory when the underlying PRO API
    call returns a low x-credits-remaining header.

    The real get_block_number tool + build_tool_response run end-to-end; only
    the HTTP transport layer is patched.  This is intentional: patching the tool
    itself (with AsyncMock returning a pre-built ToolResponse) would bypass the
    decorator/capture path and produce no advisory note.
    """
    block_payload = [{"height": 21000000, "timestamp": "2025-01-01T00:00:00.000000Z"}]
    # x-credits-remaining below the threshold so the advisory note is emitted.
    response = _MockBlockResponse(block_payload, headers={"x-credits-remaining": "3000"})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleBlockClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(bms_config, "pro_api_key", "test_key"),
        patch.object(bms_config, "pro_api_low_credits_threshold", 5000),
    ):
        http_response = await client.get("/v1/get_block_number?chain_id=1")

    assert http_response.status_code == 200
    payload = http_response.json()
    notes = payload.get("notes")
    assert notes is not None, "Expected 'notes' in response payload but got None"
    assert any("3000" in note for note in notes), f"Expected credit advisory in notes, got: {notes}"
    assert any("https://dev.blockscout.com" in note for note in notes), (
        f"Expected dev.blockscout.com URL in advisory note, got: {notes}"
    )
