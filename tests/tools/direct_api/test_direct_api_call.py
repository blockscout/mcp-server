# SPDX-License-Identifier: LicenseRef-Blockscout
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import blockscout_mcp_server.tools.direct_api.direct_api_call as direct_api_call_module
from blockscout_mcp_server.api.dependencies import MockCtx
from blockscout_mcp_server.models import DirectApiData, ToolResponse
from blockscout_mcp_server.tools.common import ResponseTooLargeError


@pytest.mark.asyncio
async def test_direct_api_call_no_params(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"result": 1}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )

        mock_request.assert_called_once_with(chain_id=chain_id, api_path=endpoint_path, params={})
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, DirectApiData)
        assert result.data.model_dump() == mock_response
        assert result.pagination is None
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_with_query_params_and_cursor(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/foo"
    mock_response = {"data": []}
    query_params = {"limit": "1"}
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.apply_cursor_to_params",
            new_callable=MagicMock,
        ) as mock_apply_cursor,
    ):
        mock_request.return_value = mock_response

        # Simulate cursor application updating params and assert inputs
        def fake_apply(cursor, params):
            assert cursor == "abc"
            assert params == {"limit": "1"}
            params.update({"page": 2})

        mock_apply_cursor.side_effect = fake_apply

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
            query_params=query_params,
            cursor="abc",
        )

        mock_apply_cursor.assert_called_once()
        mock_request.assert_called_once_with(
            chain_id=chain_id,
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
    mock_response = {"next_page_params": {"cursor": 123}, "items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )

        assert isinstance(result, ToolResponse)
        assert result.pagination is not None
        assert result.pagination.next_call.tool_name == "direct_api_call"
        nc = result.pagination.next_call.params
        assert nc["chain_id"] == chain_id
        assert nc["endpoint_path"] == endpoint_path
        assert "cursor" in nc
        assert "query_params" not in nc
        mock_request.assert_called_once_with(chain_id=chain_id, api_path=endpoint_path, params={})
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_with_query_params_pagination(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    query_params = {"sender": "0xabc"}
    mock_response = {"next_page_params": {"cursor": 456}, "items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        result = await direct_api_call_module.direct_api_call(
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
        mock_request.assert_called_once_with(chain_id=chain_id, api_path=endpoint_path, params=query_params)
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_raises_on_request_error(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.side_effect = TimeoutError("upstream timeout")
        with pytest.raises(TimeoutError):
            await direct_api_call_module.direct_api_call(
                chain_id=chain_id,
                endpoint_path=endpoint_path,
                ctx=mock_ctx,
            )
        mock_request.assert_awaited_once()
        assert mock_ctx.report_progress.await_count == 2


@pytest.mark.asyncio
async def test_direct_api_call_rejects_query_in_path(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/data?foo=bar"
    with pytest.raises(ValueError):
        await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )
    assert mock_ctx.report_progress.await_count == 1


@pytest.mark.asyncio
async def test_direct_api_call_allows_response_under_limit(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"data": "x" * 20}

    with (
        patch.object(direct_api_call_module.config, "direct_api_response_size_limit", 100),
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )

        assert isinstance(result, ToolResponse)
        assert result.data.model_dump() == mock_response


@pytest.mark.asyncio
async def test_direct_api_call_rejects_mcp_over_limit(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"data": "x" * 150}

    with (
        patch.object(direct_api_call_module.config, "direct_api_response_size_limit", 100),
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        with pytest.raises(ResponseTooLargeError):
            await direct_api_call_module.direct_api_call(
                chain_id=chain_id,
                endpoint_path=endpoint_path,
                ctx=mock_ctx,
            )


@pytest.mark.asyncio
async def test_direct_api_call_rejects_rest_over_limit_without_header():
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"data": "x" * 150}
    ctx = MockCtx(request=SimpleNamespace(headers={}))

    with (
        patch.object(direct_api_call_module.config, "direct_api_response_size_limit", 100),
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        with pytest.raises(ResponseTooLargeError):
            await direct_api_call_module.direct_api_call(
                chain_id=chain_id,
                endpoint_path=endpoint_path,
                ctx=ctx,
            )


@pytest.mark.asyncio
async def test_direct_api_call_allows_rest_over_limit_with_header():
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"data": "x" * 150}
    ctx = MockCtx(request=SimpleNamespace(headers={"X-Blockscout-Allow-Large-Response": "true"}))

    with (
        patch.object(direct_api_call_module.config, "direct_api_response_size_limit", 100),
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=ctx,
        )

        assert isinstance(result, ToolResponse)
        assert result.data.model_dump() == mock_response


@pytest.mark.asyncio
async def test_direct_api_call_list_response_wraps_payload_and_has_no_pagination(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/main-page/blocks"
    mock_response = [{"height": 1}, {"height": 2}]

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.dispatcher.dispatch", new_callable=AsyncMock
        ) as mock_dispatch,
    ):
        mock_request.return_value = mock_response
        mock_dispatch.return_value = None

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx
        )

        assert isinstance(result.data, DirectApiData)
        assert result.data.model_dump() == {"items": mock_response}
        assert result.pagination is None


@pytest.mark.asyncio
async def test_direct_api_call_list_response_content_text_item_count(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/main-page/blocks"
    mock_response = [{"height": 1}, {"height": 2}]

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.dispatcher.dispatch", new_callable=AsyncMock
        ) as mock_dispatch,
    ):
        mock_request.return_value = mock_response
        mock_dispatch.return_value = None

        result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx
        )

        assert result.content_text == f"Called {endpoint_path} on chain {chain_id}. Response type: list of 2 items."


@pytest.mark.asyncio
async def test_direct_api_call_list_response_size_limit_behavior(mock_ctx):
    chain_id = "1"
    endpoint_path = "/api/v2/main-page/blocks"
    under_limit_response = [{"height": 1}]
    over_limit_response = [{"height": i, "hash": "x" * 20} for i in range(5)]

    with (
        patch.object(direct_api_call_module.config, "direct_api_response_size_limit", 50),
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.dispatcher.dispatch", new_callable=AsyncMock
        ) as mock_dispatch,
    ):
        mock_dispatch.return_value = None
        mock_request.return_value = under_limit_response

        under_limit_result = await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )
        assert under_limit_result.data.model_dump() == {"items": under_limit_response}

        mock_request.return_value = over_limit_response
        with pytest.raises(ResponseTooLargeError):
            await direct_api_call_module.direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx)


@pytest.mark.asyncio
async def test_direct_api_call_post_basic(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request", new_callable=AsyncMock
        ) as mock_get,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_post_request",
            new_callable=AsyncMock,
        ) as mock_post,
    ):
        mock_post.return_value = {"jsonrpc": "2.0", "result": "0x1"}
        result = await direct_api_call_module.direct_api_call(
            chain_id="1", endpoint_path="/json-rpc", method="POST", json_body={"id": 1}, ctx=mock_ctx
        )
        assert isinstance(result.data, DirectApiData)
        mock_get.assert_not_called()
        mock_post.assert_awaited_once_with(
            chain_id="1",
            api_path="/json-rpc",
            json_body={"id": 1},
            params={},
        )
        assert mock_ctx.report_progress.await_count == 3


@pytest.mark.asyncio
async def test_direct_api_call_invalid_method_raises(mock_ctx):
    with pytest.raises(ValueError, match="method must be 'GET' or 'POST'"):
        await direct_api_call_module.direct_api_call(
            chain_id="1", endpoint_path="/api/v2/stats", method="PUT", ctx=mock_ctx
        )  # type: ignore[arg-type]
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_direct_api_call_get_with_json_body_raises_before_network(mock_ctx):
    with pytest.raises(ValueError, match="json_body is only allowed with method='POST'"):
        await direct_api_call_module.direct_api_call(
            chain_id="1", endpoint_path="/api/v2/stats", method="GET", json_body={"id": 1}, ctx=mock_ctx
        )
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_direct_api_call_post_without_body_raises_before_network(mock_ctx):
    with pytest.raises(ValueError, match="json_body is required when method='POST'"):
        await direct_api_call_module.direct_api_call(
            chain_id="1", endpoint_path="/json-rpc", method="POST", json_body=None, ctx=mock_ctx
        )
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_direct_api_call_post_non_dict_body_raises_before_network(mock_ctx):
    with pytest.raises(ValueError, match="json_body must be a JSON object \\(dict\\)"):
        await direct_api_call_module.direct_api_call(
            chain_id="1",
            endpoint_path="/json-rpc",
            method="POST",
            json_body="not-a-dict",  # type: ignore[arg-type]
            ctx=mock_ctx,
        )
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_direct_api_call_post_with_cursor_raises_before_network(mock_ctx):
    with pytest.raises(ValueError, match="Pagination \\(cursor\\) is not supported for POST requests"):
        await direct_api_call_module.direct_api_call(
            chain_id="1",
            endpoint_path="/json-rpc",
            method="POST",
            json_body={"id": 1},
            cursor="abc",
            ctx=mock_ctx,
        )
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_direct_api_call_post_ignores_next_page_params_for_pagination(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_post_request",
            new_callable=AsyncMock,
        ) as mock_post,
    ):
        mock_post.return_value = {"jsonrpc": "2.0", "result": "0x1", "next_page_params": {"cursor": "x"}}
        result = await direct_api_call_module.direct_api_call(
            chain_id="1", endpoint_path="/json-rpc", method="POST", json_body={"id": 1}, ctx=mock_ctx
        )
        assert result.pagination is None
        mock_post.assert_awaited_once_with(
            chain_id="1",
            api_path="/json-rpc",
            json_body={"id": 1},
            params={},
        )
        assert mock_ctx.report_progress.await_count == 3
