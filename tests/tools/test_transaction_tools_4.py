# tests/tools/test_transaction_tools_4.py
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.tools.transaction_tools import transaction_summary


@pytest.mark.asyncio
async def test_transaction_summary_invalid_format(mock_ctx):
    """Raise RuntimeError when Blockscout returns unexpected summary format."""
    chain_id = "1"
    tx_hash = "0xdeadbeef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"data": {"summaries": "unexpected"}}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        with pytest.raises(RuntimeError):
            await transaction_summary(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{tx_hash}/summary",
        )
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3
