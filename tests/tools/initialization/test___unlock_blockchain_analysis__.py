# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import patch

import pytest

from blockscout_mcp_server.constants import SKILL_RESOLUTION_RULE_TEXT
from blockscout_mcp_server.models import InstructionsData, ToolResponse
from blockscout_mcp_server.resources import skill_resources
from blockscout_mcp_server.server import composed_instructions
from blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis import __unlock_blockchain_analysis__


@pytest.mark.asyncio
async def test_unlock_blockchain_analysis_success(mock_ctx):
    """Verify __unlock_blockchain_analysis__ returns a structured ToolResponse[InstructionsData]."""
    # ARRANGE
    mock_version = "1.2.3"
    mock_pointer = "Test skill pointer sentence."
    mock_resolution_rule = "Test skill resolution rule."
    with (
        patch("blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.SERVER_VERSION", mock_version),
        patch(
            "blockscout_mcp_server.resources.skill_resources.skill_pointer_text",
            return_value=mock_pointer,
        ),
        patch(
            "blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis.SKILL_RESOLUTION_RULE_TEXT",
            mock_resolution_rule,
        ),
    ):
        # ACT
        result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, InstructionsData)

        assert result.data.version == mock_version
        assert result.data.skill_reference == mock_pointer
        assert result.data.skill_resolution_rule == mock_resolution_rule

        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

        start_call = mock_ctx.report_progress.call_args_list[0]
        assert start_call.kwargs["progress"] == 0.0
        assert "Fetching server instructions" in start_call.kwargs["message"]

        end_call = mock_ctx.report_progress.call_args_list[1]
        assert end_call.kwargs["progress"] == 1.0
        assert "Server instructions ready" in end_call.kwargs["message"]


@pytest.mark.asyncio
async def test_unlock_payload_skill_text_matches_server_instructions(mock_ctx):
    result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

    assert result.data.skill_reference == skill_resources.skill_pointer_text()
    assert result.data.skill_resolution_rule == SKILL_RESOLUTION_RULE_TEXT
    assert f"{result.data.skill_reference}\n\n{result.data.skill_resolution_rule}" in composed_instructions
