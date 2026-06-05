# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import BlockInfoData, ToolResponse
from blockscout_mcp_server.tools.block.get_block_info import get_block_info
from blockscout_mcp_server.tools.common import CreditsExhaustedError


@pytest.mark.asyncio
async def test_get_block_info_success_no_txs(mock_ctx):
    """Verify get_block_info returns structured data without transactions."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_api_response = {"height": 19000000, "timestamp": "2023-01-01T00:00:00Z"}

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.return_value = mock_api_response

        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, ctx=mock_ctx)

        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/blocks/{number_or_hash}",
            timeout=config.bs_light_timeout,
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_api_response
        assert result.data.transaction_hashes is None
        assert result.notes is None
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        assert "mined at" in result.content_text


@pytest.mark.asyncio
async def test_get_block_info_with_txs_success(mock_ctx):
    """Verify get_block_info returns structured data with a list of transaction hashes."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_block_response = {"height": 19000000, "transactions_count": 2}
    mock_txs_response = {"items": [{"hash": "0xtx1"}, {"hash": "0xtx2"}]}

    async def mock_request_side_effect(chain_id, api_path, params=None, **kwargs):
        if "transactions" in api_path:
            return mock_txs_response
        return mock_block_response

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        mock_request.assert_has_awaits(
            [
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/blocks/{number_or_hash}",
                    timeout=config.bs_light_timeout,
                ),
                call(chain_id=chain_id, api_path=f"/api/v2/blocks/{number_or_hash}/transactions"),
            ],
            any_order=True,
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes == ["0xtx1", "0xtx2"]
        assert result.notes is None
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert "transactions, mined at" in result.content_text


@pytest.mark.asyncio
async def test_get_block_info_with_txs_partial_failure(mock_ctx):
    """Verify get_block_info handles failure when fetching transactions but not block info."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_block_response = {"height": 19000000}
    tx_error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    async def mock_request_side_effect(chain_id, api_path, params=None, **kwargs):
        if "transactions" in api_path:
            raise tx_error
        return mock_block_response

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        mock_request.assert_has_awaits(
            [
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/blocks/{number_or_hash}",
                    timeout=config.bs_light_timeout,
                ),
                call(chain_id=chain_id, api_path=f"/api/v2/blocks/{number_or_hash}/transactions"),
            ],
            any_order=True,
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes is None
        assert result.notes is not None
        assert "Could not retrieve the list of transactions" in result.notes[0]
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        # Watershed beat (index 1) must carry the neutral message and total=2.0
        watershed_call = mock_ctx.report_progress.await_args_list[1]
        assert watershed_call.kwargs["message"] == "Block and transaction requests completed; processing results."
        assert watershed_call.kwargs["total"] == 2.0


@pytest.mark.asyncio
async def test_get_block_info_total_failure(mock_ctx):
    """Verify get_block_info raises an exception if the main block call fails."""
    chain_id = "1"
    number_or_hash = "19000000"
    block_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    async def mock_request_side_effect(chain_id, api_path, params=None, **kwargs):
        if "transactions" in api_path:
            return {"items": []}
        raise block_error

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = mock_request_side_effect

        with pytest.raises(httpx.HTTPStatusError):
            await get_block_info(
                chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
            )
        assert mock_request.await_count == 2
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        # Watershed beat (index 1) must carry the neutral message and total=2.0
        watershed_call = mock_ctx.report_progress.await_args_list[1]
        assert watershed_call.kwargs["message"] == "Block and transaction requests completed; processing results."
        assert watershed_call.kwargs["total"] == 2.0


@pytest.mark.asyncio
async def test_get_block_info_no_txs_upstream_failure(mock_ctx):
    """Verify get_block_info (no-transactions branch) emits only the start beat when the request fails."""
    chain_id = "1"
    number_or_hash = "19000000"

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = ValueError("upstream error")

        with pytest.raises(ValueError, match="upstream error"):
            await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, ctx=mock_ctx)

        assert mock_ctx.report_progress.await_count == 1
        assert mock_ctx.info.await_count == 1


@pytest.mark.asyncio
async def test_get_block_info_with_txs_credits_exhausted_degrades_gracefully(mock_ctx):
    """CreditsExhaustedError on the transactions side request degrades softly.

    Mirrors test_get_block_info_with_txs_partial_failure but with the new
    exception type to prove the composite-tool soft-fail path handles it.
    """
    chain_id = "1"
    number_or_hash = "19000000"
    mock_block_response = {"height": 19000000}
    tx_error = CreditsExhaustedError(
        "Blockscout PRO API credits exhausted (HTTP 402): the API key's credit allowance is depleted."
    )

    async def mock_request_side_effect(chain_id, api_path, params=None, **kwargs):
        if "transactions" in api_path:
            raise tx_error
        return mock_block_response

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes is None
        assert result.notes is not None
        assert "Could not retrieve the list of transactions" in result.notes[0]
