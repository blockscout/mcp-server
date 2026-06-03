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
        assert mock_ctx.report_progress.await_count == 1


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
        assert mock_ctx.report_progress.await_count == 1


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
        assert mock_ctx.report_progress.await_count == 1


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
        assert mock_ctx.report_progress.await_count == 1
