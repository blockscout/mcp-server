# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import patch

import pytest

from blockscout_mcp_server import session_gate
from blockscout_mcp_server.constants import SKILL_RESOLUTION_RULE_TEXT
from blockscout_mcp_server.models import InstructionsData, ToolResponse
from blockscout_mcp_server.resources import skill_resources
from blockscout_mcp_server.server import composed_instructions
from blockscout_mcp_server.session_store import get_store
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

        assert result.data.server_version == mock_version
        assert result.instructions == [mock_pointer, mock_resolution_rule]

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

    assert result.instructions == [
        skill_resources.skill_pointer_text(),
        SKILL_RESOLUTION_RULE_TEXT,
    ]
    pointer_text, resolution_rule_text = result.instructions
    assert f"{pointer_text}\n\n{resolution_rule_text}" in composed_instructions


_UNGATED_CONTENT_TEXT = (
    "Consult the `blockscout-analysis` skill referenced in the response before invoking any other tool."
)


@pytest.mark.asyncio
async def test_ungated_session_id_is_none_and_absent_from_payload(mock_ctx):
    """Ungated (default config): no session_id on the object or in the serialized payload,
    and content_text is unchanged from today."""
    result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

    assert result.data.session_id is None
    dumped = result.data.model_dump(mode="json", by_alias=True)
    assert "session_id" not in dumped
    assert result.content_text.endswith(_UNGATED_CONTENT_TEXT)


@pytest.mark.asyncio
async def test_gated_session_id_is_minted_and_no_store_row_written(enabled_session_gate, mock_ctx):
    """Gated: data.session_id is a token session_gate.verify_token accepts, no store row is
    written (lazy creation - unlock stays a pure function), and content_text is the exact
    templated string."""
    result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

    assert result.data.session_id is not None
    random_part, _issued_at = session_gate.verify_token(result.data.session_id)

    store = get_store()
    row = store._conn.execute(  # noqa: SLF001 - direct row-existence check, no public API for this
        "SELECT 1 FROM sessions WHERE id = :id", {"id": random_part}
    ).fetchone()
    assert row is None

    expected_content_text = (
        f"Session initialized (server v{result.data.server_version}). Consult the `blockscout-analysis` skill "
        "referenced in the response before invoking any other tool. Your `session_id` is "
        f"`{result.data.session_id}` — pass it with every subsequent tool call. A session is this entire "
        "conversation, including all tool loops and sub-agents; reconnections and context compaction do "
        "not start a new one. Do not initialize this session again."
    )
    assert result.content_text == expected_content_text
    assert result.data.session_id in result.content_text


@pytest.mark.asyncio
async def test_gated_session_id_serialized_payload_includes_key(enabled_session_gate, mock_ctx):
    """Gated: serialized payload includes the session_id key with the minted value."""
    result = await __unlock_blockchain_analysis__(ctx=mock_ctx)

    dumped = result.data.model_dump(mode="json", by_alias=True)
    assert dumped["session_id"] == result.data.session_id


@pytest.mark.asyncio
async def test_two_gated_calls_return_different_identifiers(enabled_session_gate, mock_ctx):
    """Two gated calls mint fresh, distinct identifiers (fresh randomness each mint)."""
    first = await __unlock_blockchain_analysis__(ctx=mock_ctx)
    second = await __unlock_blockchain_analysis__(ctx=mock_ctx)

    assert first.data.session_id != second.data.session_id
