from unittest.mock import patch

import pytest

from blockscout_mcp_server.models import InstructionsData, ToolResponse
from blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis import __unlock_blockchain_analysis__


@pytest.mark.asyncio
async def test_unlock_blockchain_analysis_success(mock_ctx):
    """Verify __unlock_blockchain_analysis__ returns a structured ToolResponse[InstructionsData]."""
    # ARRANGE
    mock_version = "1.2.3"
    mock_error_rules = "Error handling rule."
    mock_chain_rules = "Chain ID rule."
    mock_pagination_rules = "Pagination rule."
    mock_time_rules = "Time-based query rule."
    mock_binary_search_rules = "Binary search rule."
    mock_portfolio_rules = "Portfolio analysis rule."
    mock_funds_movement_rules = "Funds movement rule."
    mock_data_ordering_rules = "Data ordering rule."
    mock_chains = [
        {
            "name": "TestChain",
            "chain_id": "999",
            "is_testnet": False,
            "native_currency": "TST",
            "ecosystem": "Test",
            "settlement_layer_chain_id": "1",
        }
    ]

    with (
        patch("blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.SERVER_VERSION", mock_version),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.ERROR_HANDLING_RULES",
            mock_error_rules,
        ),
        patch("blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.CHAIN_ID_RULES", mock_chain_rules),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.PAGINATION_RULES",
            mock_pagination_rules,
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.TIME_BASED_QUERY_RULES",
            mock_time_rules,
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.BINARY_SEARCH_RULES",
            mock_binary_search_rules,
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.PORTFOLIO_ANALYSIS_RULES",
            mock_portfolio_rules,
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.FUNDS_MOVEMENT_RULES",
            mock_funds_movement_rules,
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.DATA_ORDERING_AND_RESUMPTION_RULES",
            mock_data_ordering_rules,
        ),
        patch("blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.RECOMMENDED_CHAINS", mock_chains),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.DIRECT_API_CALL_RULES",
            "Direct API rule",
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.DIRECT_API_CALL_ENDPOINT_LIST",
            {"common": [], "specific": []},
        ),
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
        assert first_chain.settlement_layer_chain_id == "1"
        assert result.data.pagination_rules == mock_pagination_rules
        assert result.data.time_based_query_rules == mock_time_rules
        assert result.data.binary_search_rules == mock_binary_search_rules
        assert result.data.portfolio_analysis_rules == mock_portfolio_rules
        assert result.data.funds_movement_rules == mock_funds_movement_rules
        assert result.data.data_ordering_and_resumption_rules == mock_data_ordering_rules
        assert result.data.direct_api_call_rules == "Direct API rule"
        assert result.data.direct_api_endpoints.common == []

        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

        start_call = mock_ctx.report_progress.call_args_list[0]
        assert start_call.kwargs["progress"] == 0.0
        assert "Fetching server instructions" in start_call.kwargs["message"]

        end_call = mock_ctx.report_progress.call_args_list[1]
        assert end_call.kwargs["progress"] == 1.0
        assert "Server instructions ready" in end_call.kwargs["message"]
