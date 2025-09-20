import pytest

from blockscout_mcp_server.models import ToolResponse, TransactionSummaryData
from blockscout_mcp_server.tools.transaction.transaction_summary import transaction_summary


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_summary_integration(mock_ctx):
    """Ensure transaction_summary returns structured data for a stable transaction."""
    tx_hash = "0x5c7f2f244d91ec281c738393da0be6a38bc9045e29c0566da8c11e7a2f7cbc64"
    result = await transaction_summary(chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)

    assert result.data.summary is None or isinstance(result.data.summary, list)
    if isinstance(result.data.summary, list):
        assert len(result.data.summary) > 0
