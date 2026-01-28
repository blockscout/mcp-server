import pytest

from blockscout_mcp_server.models import ToolResponse, TransactionSummaryData
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_transaction_summary_integration(mock_ctx):
    """Tests that direct_api_call dispatches transaction summary and validates the schema."""
    tx_hash = "0x5c7f2f244d91ec281c738393da0be6a38bc9045e29c0566da8c11e7a2f7cbc64"
    endpoint_path = f"/api/v2/transactions/{tx_hash}/summary"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call transaction summary request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)

    assert result.data.summary is None or isinstance(result.data.summary, list)
    if isinstance(result.data.summary, list):
        assert len(result.data.summary) > 0
        assert isinstance(result.data.summary[0], dict)
