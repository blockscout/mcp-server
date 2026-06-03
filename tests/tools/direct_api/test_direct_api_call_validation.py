# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

import blockscout_mcp_server.tools.direct_api.direct_api_call as direct_api_call_module


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_get(mock_ctx):
    """GET request to /api/eth-rpc raises ValueError before any network call."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="/json-rpc"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/api/eth-rpc",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_trailing_slash(mock_ctx):
    """GET request to /api/eth-rpc/ (trailing slash) raises ValueError before any network call."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="/json-rpc"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/api/eth-rpc/",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_post(mock_ctx):
    """POST request to /api/eth-rpc raises ValueError before any network call."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_post_request",
            new_callable=AsyncMock,
        ) as mock_post,
    ):
        with pytest.raises(ValueError, match="/json-rpc"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/api/eth-rpc",
                method="POST",
                json_body={"id": 1},
                ctx=mock_ctx,
            )
        mock_post.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_case_insensitive(mock_ctx):
    """Case-insensitive variant /API/ETH-RPC raises ValueError before any network call."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="/json-rpc"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/API/ETH-RPC",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_with_query_string(mock_ctx):
    """A trailing query string still yields the legacy-path error, not the generic query-param one."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="no longer supported"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/api/eth-rpc?id=1",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_surrounding_whitespace(mock_ctx):
    """Surrounding whitespace around the legacy path raises ValueError before any network call."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="/json-rpc"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="  /api/eth-rpc  ",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_trailing_slash_with_query_string(mock_ctx):
    """A trailing slash combined with a query string still yields the legacy-path error."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="no longer supported"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/api/eth-rpc/?id=1",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_rejects_legacy_eth_rpc_path_whitespace_before_query_string(mock_ctx):
    """Whitespace between the legacy path and its query string still yields the legacy-path error."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="no longer supported"):
            await direct_api_call_module.direct_api_call(
                chain_id="1",
                endpoint_path="/api/eth-rpc ?id=1",
                ctx=mock_ctx,
            )
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_api_call_allows_non_legacy_lookalike_path(mock_ctx):
    """A path that merely contains 'eth-rpc' as a substring is not rejected and reaches the network."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        mock_get.return_value = {"result": "ok"}
        await direct_api_call_module.direct_api_call(
            chain_id="1",
            endpoint_path="/api/eth-rpc-foo",
            ctx=mock_ctx,
        )
        mock_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_direct_api_call_allows_supported_json_rpc_path(mock_ctx):
    """The supported /json-rpc path is not rejected and reaches the network."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_post_request",
            new_callable=AsyncMock,
        ) as mock_post,
    ):
        mock_post.return_value = {"jsonrpc": "2.0", "id": 1, "result": "0x1"}
        await direct_api_call_module.direct_api_call(
            chain_id="1",
            endpoint_path="/json-rpc",
            method="POST",
            json_body={"jsonrpc": "2.0", "method": "eth_blockNumber", "id": 1},
            ctx=mock_ctx,
        )
        mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_direct_api_call_strips_whitespace_around_supported_path(mock_ctx):
    """Surrounding whitespace on a supported path is normalized before the network call."""
    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_get,
    ):
        mock_get.return_value = {"result": "ok"}
        await direct_api_call_module.direct_api_call(
            chain_id="1",
            endpoint_path="  /api/v2/stats  ",
            ctx=mock_ctx,
        )
        mock_get.assert_awaited_once()
        assert mock_get.await_args.kwargs["api_path"] == "/api/v2/stats"
