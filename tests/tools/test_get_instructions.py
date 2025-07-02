from unittest.mock import patch

import pytest

from blockscout_mcp_server.models import InstructionsData, ToolResponse
from blockscout_mcp_server.tools.get_instructions import __get_instructions__


@pytest.mark.asyncio
async def test_get_instructions_success(mock_ctx):
    """Verify __get_instructions__ returns a structured ToolResponse[InstructionsData]."""
    # ARRANGE
    mock_version = "1.2.3"
    mock_rules = ["Rule 1.", "Rule 2."]
    mock_chains = [{"name": "TestChain", "chain_id": "999"}]

    with (
        patch("blockscout_mcp_server.tools.get_instructions.SERVER_VERSION", mock_version),
        patch("blockscout_mcp_server.tools.get_instructions.GENERAL_RULES", mock_rules),
        patch("blockscout_mcp_server.tools.get_instructions.RECOMMENDED_CHAINS", mock_chains),
    ):
        # ACT
        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, InstructionsData)

        assert result.data.version == mock_version
        assert result.data.general_rules == mock_rules
        assert len(result.data.recommended_chains) == 1
        assert result.data.recommended_chains[0].name == "TestChain"
        assert result.data.recommended_chains[0].chain_id == "999"

        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

        start_call = mock_ctx.report_progress.call_args_list[0]
        assert start_call.kwargs["progress"] == 0.0
        assert "Fetching server instructions" in start_call.kwargs["message"]

        end_call = mock_ctx.report_progress.call_args_list[1]
        assert end_call.kwargs["progress"] == 1.0
        assert "Server instructions ready" in end_call.kwargs["message"]
