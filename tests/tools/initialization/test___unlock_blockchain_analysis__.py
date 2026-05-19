# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import patch

import pytest

from blockscout_mcp_server.models import InstructionsData, ToolResponse
from blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis import __unlock_blockchain_analysis__


@pytest.mark.asyncio
async def test_unlock_blockchain_analysis_success(mock_ctx):
    """Verify __unlock_blockchain_analysis__ returns a structured ToolResponse[InstructionsData]."""
    # ARRANGE
    mock_version = "1.2.3"
    mock_pointer = "Test skill pointer sentence."
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
        patch("blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.RECOMMENDED_CHAINS", mock_chains),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.SKILL_POINTER_TEXT",
            mock_pointer,
        ),
    ):
        # ACT
        result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, InstructionsData)

        assert result.data.version == mock_version
        assert result.data.skill_reference == mock_pointer

        assert isinstance(result.data.recommended_chains, list)
        assert len(result.data.recommended_chains) == 1
        first_chain = result.data.recommended_chains[0]
        assert first_chain.name == "TestChain"
        assert first_chain.chain_id == "999"
        assert first_chain.is_testnet is False
        assert first_chain.native_currency == "TST"
        assert first_chain.ecosystem == "Test"
        assert first_chain.settlement_layer_chain_id == "1"

        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

        start_call = mock_ctx.report_progress.call_args_list[0]
        assert start_call.kwargs["progress"] == 0.0
        assert "Fetching server instructions" in start_call.kwargs["message"]

        end_call = mock_ctx.report_progress.call_args_list[1]
        assert end_call.kwargs["progress"] == 1.0
        assert "Server instructions ready" in end_call.kwargs["message"]
