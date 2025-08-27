from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.tools.direct_api_tools import direct_api_call


@pytest.mark.asyncio
async def test_direct_api_call_no_params(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_base_url = "https://eth.blockscout.com"
    mock_response = {"result": 1}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_response

        result = await direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=endpoint_path, params={})
        assert isinstance(result, ToolResponse)
        assert result.data == mock_response
        assert result.pagination is None


@pytest.mark.asyncio
async def test_direct_api_call_with_query_params_and_cursor(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/foo"
    mock_base_url = "https://eth.blockscout.com"
    mock_response = {"data": []}
    query_params = {"limit": "1"}
    decoded_cursor = {"page": 2}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.decode_cursor",
            return_value=decoded_cursor,
        ) as mock_decode,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_response

        result = await direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
            query_params=query_params,
            cursor="abc",
        )

        mock_get_url.assert_called_once_with(chain_id)
        mock_decode.assert_called_once_with("abc")
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=endpoint_path,
            params={"limit": "1", "page": 2},
        )
        assert isinstance(result, ToolResponse)
        assert result.pagination is None


@pytest.mark.asyncio
async def test_direct_api_call_with_pagination(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    mock_base_url = "https://eth.blockscout.com"
    mock_response = {"next_page_params": {"cursor": 123}, "items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_response

        result = await direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert result.pagination is not None
        assert result.pagination.next_call.tool_name == "direct_api_call"
        assert "cursor" in result.pagination.next_call.params
