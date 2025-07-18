from unittest.mock import MagicMock, patch

import pytest

from blockscout_mcp_server.models import (
    EmptyData,
    InstructionsData,
    ToolResponse,
)
from blockscout_mcp_server.tools.get_instructions import (
    __get_instructions__,
    is_modern_protocol_version,
)


@pytest.mark.asyncio
async def test_get_instructions_modern_client(mock_ctx):
    """Modern clients receive structured InstructionsData in the instructions field."""
    # ARRANGE
    mock_version = "1.2.3"
    mock_error_rules = "Error handling rule."
    mock_chain_rules = "Chain ID rule."
    mock_pagination_rules = "Pagination rule."
    mock_time_rules = "Time-based query rule."
    mock_block_rules = "Block time estimation rule."
    mock_efficiency_rules = "Efficiency optimization rule."
    mock_chains = [{"name": "TestChain", "chain_id": "999"}]

    with (
        patch("blockscout_mcp_server.tools.get_instructions.SERVER_VERSION", mock_version),
        patch("blockscout_mcp_server.tools.get_instructions.ERROR_HANDLING_RULES", mock_error_rules),
        patch("blockscout_mcp_server.tools.get_instructions.CHAIN_ID_RULES", mock_chain_rules),
        patch("blockscout_mcp_server.tools.get_instructions.PAGINATION_RULES", mock_pagination_rules),
        patch("blockscout_mcp_server.tools.get_instructions.TIME_BASED_QUERY_RULES", mock_time_rules),
        patch("blockscout_mcp_server.tools.get_instructions.BLOCK_TIME_ESTIMATION_RULES", mock_block_rules),
        patch("blockscout_mcp_server.tools.get_instructions.EFFICIENCY_OPTIMIZATION_RULES", mock_efficiency_rules),
        patch("blockscout_mcp_server.tools.get_instructions.RECOMMENDED_CHAINS", mock_chains),
    ):
        # ACT
        # Provide protocolVersion
        mock_ctx.session = MagicMock()
        mock_ctx.session.client_params = MagicMock()
        mock_ctx.session.client_params.protocolVersion = "2025-06-18"

        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, EmptyData)
        assert isinstance(result.instructions, InstructionsData)
        assert result.instructions.version == mock_version
        assert result.instructions.error_handling_rules == mock_error_rules
        assert result.instructions.chain_id_guidance.rules == mock_chain_rules
        assert len(result.instructions.chain_id_guidance.recommended_chains) == 1
        assert result.instructions.chain_id_guidance.recommended_chains[0].name == "TestChain"
        assert result.instructions.chain_id_guidance.recommended_chains[0].chain_id == "999"
        assert result.instructions.pagination_rules == mock_pagination_rules
        assert result.instructions.time_based_query_rules == mock_time_rules
        assert result.instructions.block_time_estimation_rules == mock_block_rules
        assert result.instructions.efficiency_optimization_rules == mock_efficiency_rules

        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

        start_call = mock_ctx.report_progress.call_args_list[0]
        assert start_call.kwargs["progress"] == 0.0
        assert "Fetching server instructions" in start_call.kwargs["message"]

        end_call = mock_ctx.report_progress.call_args_list[1]
        assert end_call.kwargs["progress"] == 1.0
        assert "Server instructions ready" in end_call.kwargs["message"]


def test_is_modern_protocol_version():
    assert is_modern_protocol_version("2025-06-18")
    assert is_modern_protocol_version("2026-01-01")
    assert not is_modern_protocol_version("2025-06-17")
    assert not is_modern_protocol_version(None)
    assert not is_modern_protocol_version("invalid")


@pytest.mark.asyncio
async def test_get_instructions_legacy_client(mock_ctx):
    """Legacy clients receive XML instruction strings."""
    mock_ctx.session = MagicMock()
    mock_ctx.session.client_params = MagicMock()
    mock_ctx.session.client_params.protocolVersion = "2024-01-01"

    result = await __get_instructions__(ctx=mock_ctx)

    assert isinstance(result.data, EmptyData)
    assert isinstance(result.instructions, list)
    assert any("<error_handling_rules>" in s for s in result.instructions)


@pytest.mark.asyncio
async def test_get_instructions_rest_api(mock_ctx):
    """No protocol version behaves like legacy client."""
    result = await __get_instructions__(ctx=mock_ctx)

    assert isinstance(result.data, EmptyData)
    assert isinstance(result.instructions, list)
    assert any("<chain_id_guidance>" in s for s in result.instructions)
