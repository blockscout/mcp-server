from unittest.mock import patch

import pytest

from blockscout_mcp_server.models import InstructionsData, ToolResponse
from blockscout_mcp_server.tools.initialization_tools import __unlock_blockchain_analysis__


@pytest.mark.asyncio
async def test_unlock_blockchain_analysis_success(mock_ctx):
    """Verify __unlock_blockchain_analysis__ returns a structured ToolResponse[InstructionsData]."""
    # ARRANGE
    mock_version = "1.2.3"
    mock_error_rules = "Error handling rule."
    mock_chain_rules = "Chain ID rule."
    mock_pagination_rules = "Pagination rule."
    mock_time_rules = "Time-based query rule."
    mock_block_rules = "Block time estimation rule."
    mock_efficiency_rules = "Efficiency optimization rule."
    mock_chains = [
        {
            "name": "TestChain",
            "chain_id": "999",
            "is_testnet": False,
            "native_currency": "TST",
            "ecosystem": "Test",
        }
    ]

    with (
        patch("blockscout_mcp_server.tools.initialization_tools.SERVER_VERSION", mock_version),
        patch("blockscout_mcp_server.tools.initialization_tools.ERROR_HANDLING_RULES", mock_error_rules),
        patch("blockscout_mcp_server.tools.initialization_tools.CHAIN_ID_RULES", mock_chain_rules),
        patch("blockscout_mcp_server.tools.initialization_tools.PAGINATION_RULES", mock_pagination_rules),
        patch("blockscout_mcp_server.tools.initialization_tools.TIME_BASED_QUERY_RULES", mock_time_rules),
        patch("blockscout_mcp_server.tools.initialization_tools.BLOCK_TIME_ESTIMATION_RULES", mock_block_rules),
        patch("blockscout_mcp_server.tools.initialization_tools.EFFICIENCY_OPTIMIZATION_RULES", mock_efficiency_rules),
        patch("blockscout_mcp_server.tools.initialization_tools.RECOMMENDED_CHAINS", mock_chains),
    ):
        # ACT
        result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, InstructionsData)

        assert result.data.version == mock_version
        assert result.data.error_handling_rules == mock_error_rules
        assert result.data.chain_id_guidance.rules == mock_chain_rules
        assert len(result.data.chain_id_guidance.recommended_chains) == 1
        first_chain = result.data.chain_id_guidance.recommended_chains[0]
        assert first_chain.name == "TestChain"
        assert first_chain.chain_id == "999"
        assert first_chain.is_testnet is False
        assert first_chain.native_currency == "TST"
        assert first_chain.ecosystem == "Test"
        assert result.data.pagination_rules == mock_pagination_rules
        assert result.data.time_based_query_rules == mock_time_rules
        assert result.data.block_time_estimation_rules == mock_block_rules
        assert result.data.efficiency_optimization_rules == mock_efficiency_rules

        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

        start_call = mock_ctx.report_progress.call_args_list[0]
        assert start_call.kwargs["progress"] == 0.0
        assert "Fetching server instructions" in start_call.kwargs["message"]

        end_call = mock_ctx.report_progress.call_args_list[1]
        assert end_call.kwargs["progress"] == 1.0
        assert "Server instructions ready" in end_call.kwargs["message"]
