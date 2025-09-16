from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockscout_mcp_server.models import DirectApiData, ToolResponse
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
        assert isinstance(result.data, DirectApiData)
        assert result.data.model_dump() == mock_response
        assert result.pagination is None
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_with_query_params_and_cursor(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/foo"
    mock_base_url = "https://eth.blockscout.com"
    mock_response = {"data": []}
    query_params = {"limit": "1"}
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
            "blockscout_mcp_server.tools.direct_api_tools.apply_cursor_to_params",
            new_callable=MagicMock,
        ) as mock_apply_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_response

        # Simulate cursor application updating params and assert inputs
        def fake_apply(cursor, params):
            assert cursor == "abc"
            assert params == {"limit": "1"}
            params.update({"page": 2})

        mock_apply_cursor.side_effect = fake_apply

        result = await direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
            query_params=query_params,
            cursor="abc",
        )

        mock_get_url.assert_called_once_with(chain_id)
        mock_apply_cursor.assert_called_once()
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=endpoint_path,
            params={"limit": "1", "page": 2},
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, DirectApiData)
        assert result.data.model_dump() == mock_response
        assert result.pagination is None
        assert mock_ctx.report_progress.await_count == 3


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
        nc = result.pagination.next_call.params
        assert nc["chain_id"] == chain_id
        assert nc["endpoint_path"] == endpoint_path
        assert "cursor" in nc
        assert "query_params" not in nc
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=endpoint_path, params={})
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_with_query_params_pagination(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    query_params = {"sender": "0xabc"}
    mock_base_url = "https://eth.blockscout.com"
    mock_response = {"next_page_params": {"cursor": 456}, "items": []}

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

        result = await direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            query_params=query_params,
            ctx=mock_ctx,
        )

        assert isinstance(result, ToolResponse)
        assert result.pagination is not None
        nc = result.pagination.next_call.params
        assert nc["chain_id"] == chain_id
        assert nc["endpoint_path"] == endpoint_path
        assert nc["query_params"] == query_params
        assert "cursor" in nc
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=endpoint_path, params=query_params)
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_raises_on_request_error(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    mock_base_url = "https://eth.blockscout.com"
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
        mock_request.side_effect = TimeoutError("upstream timeout")
        with pytest.raises(TimeoutError):
            await direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx)
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_awaited_once()
        assert mock_ctx.report_progress.await_count == 2


@pytest.mark.asyncio
async def test_direct_api_call_rejects_query_in_path(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data?foo=bar"
    mock_base_url = "https://eth.blockscout.com"
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
    ):
        mock_get_url.return_value = mock_base_url
        with pytest.raises(ValueError):
            await direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx)
        mock_get_url.assert_called_once_with(chain_id)
        assert mock_ctx.report_progress.await_count == 1
