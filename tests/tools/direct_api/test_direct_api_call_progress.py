# SPDX-License-Identifier: LicenseRef-Blockscout
"""Progress-focused tests for direct_api_call (companion to test_direct_api_call.py).

Covers: start-message naming, " (next page)" suffix, large-response
completion-ordering, and query-string leak-guard.  Kept in a separate module
to stay within the 500-LOC cap on the main test file (rule 210 / rule 010 §6).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import blockscout_mcp_server.tools.direct_api.direct_api_call as direct_api_call_module
from blockscout_mcp_server.tools.common import ResponseTooLargeError

# ---------------------------------------------------------------------------
# Start-message naming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_message_names_method_and_endpoint_get(mock_ctx):
    """Start beat carries the HTTP method and endpoint path for a GET request."""
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"result": 1}

    with patch(
        "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = mock_response

        await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )

    # First report_progress call is the start beat
    first_call_kwargs = mock_ctx.report_progress.await_args_list[0].kwargs
    assert first_call_kwargs["progress"] == 0.0
    assert first_call_kwargs["total"] == 1.0
    assert "GET" in first_call_kwargs["message"]
    assert endpoint_path in first_call_kwargs["message"]
    assert chain_id in first_call_kwargs["message"]


@pytest.mark.asyncio
async def test_start_message_names_method_and_endpoint_post(mock_ctx):
    """Start beat carries the HTTP method and endpoint path for a POST request."""
    chain_id = "42"
    endpoint_path = "/json-rpc"

    with patch(
        "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_post_request",
        new_callable=AsyncMock,
    ) as mock_post:
        mock_post.return_value = {"jsonrpc": "2.0", "result": "0x1"}

        await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            method="POST",
            json_body={"id": 1},
            ctx=mock_ctx,
        )

    first_call_kwargs = mock_ctx.report_progress.await_args_list[0].kwargs
    assert first_call_kwargs["progress"] == 0.0
    assert first_call_kwargs["total"] == 1.0
    assert "POST" in first_call_kwargs["message"]
    assert endpoint_path in first_call_kwargs["message"]
    assert chain_id in first_call_kwargs["message"]


@pytest.mark.asyncio
async def test_start_message_names_method_and_endpoint_handler_path(mock_ctx):
    """Start beat carries method and endpoint when a specialized handler returns a response."""
    chain_id = "1"
    endpoint_path = "/api/v2/addresses"
    mock_response = {"items": []}
    handler_result = MagicMock()

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.dispatcher.dispatch",
            new_callable=AsyncMock,
        ) as mock_dispatch,
    ):
        mock_request.return_value = mock_response
        mock_dispatch.return_value = handler_result

        await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )

    first_call_kwargs = mock_ctx.report_progress.await_args_list[0].kwargs
    assert "GET" in first_call_kwargs["message"]
    assert endpoint_path in first_call_kwargs["message"]
    assert chain_id in first_call_kwargs["message"]
    # Completion beat fires too (handler path)
    assert mock_ctx.report_progress.await_count == 2


# ---------------------------------------------------------------------------
# " (next page)" suffix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_message_has_next_page_suffix_when_cursor_provided(mock_ctx):
    """Start beat appends ' (next page)' when a pagination cursor is supplied."""
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    mock_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.apply_cursor_to_params",
            new_callable=MagicMock,
        ),
    ):
        mock_request.return_value = mock_response

        await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            cursor="some-cursor",
            ctx=mock_ctx,
        )

    first_call_kwargs = mock_ctx.report_progress.await_args_list[0].kwargs
    assert " (next page)" in first_call_kwargs["message"]


@pytest.mark.asyncio
async def test_start_message_has_no_next_page_suffix_without_cursor(mock_ctx):
    """Start beat does NOT contain ' (next page)' when no cursor is supplied."""
    chain_id = "1"
    endpoint_path = "/api/v2/data"
    mock_response = {"items": []}

    with patch(
        "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = mock_response

        await direct_api_call_module.direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            ctx=mock_ctx,
        )

    first_call_kwargs = mock_ctx.report_progress.await_args_list[0].kwargs
    assert " (next page)" not in first_call_kwargs["message"]


# ---------------------------------------------------------------------------
# Large-response completion-ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_large_response_mcp_both_beats_fire_before_error(mock_ctx):
    """Both start and completion beats fire before ResponseTooLargeError is raised (non-REST)."""
    chain_id = "1"
    endpoint_path = "/api/v2/stats"
    mock_response = {"data": "x" * 150}

    with (
        patch.object(direct_api_call_module.config, "direct_api_response_size_limit", 100),
        patch(
            "blockscout_mcp_server.tools.direct_api.direct_api_call.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_request.return_value = mock_response

        with pytest.raises(ResponseTooLargeError):
            await direct_api_call_module.direct_api_call(
                chain_id=chain_id,
                endpoint_path=endpoint_path,
                ctx=mock_ctx,
            )

    # Both start (progress=0.0) and completion (progress=1.0) beats must have fired
    assert mock_ctx.report_progress.await_count == 2
    progress_values = [call.kwargs["progress"] for call in mock_ctx.report_progress.await_args_list]
    assert progress_values == [0.0, 1.0]


# ---------------------------------------------------------------------------
# Query-string leak-guard (DD-01 security intent)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_string_in_path_emits_zero_beats_and_logs_nothing(mock_ctx):
    """A query string in endpoint_path emits zero progress beats and zero info logs.

    Primary guard: if a regression re-orders the start beat ahead of the '?' check,
    the start message would echo the path — including any embedded secrets — through
    both report_progress and ctx.info before the ValueError fires.
    """
    with pytest.raises(ValueError):
        await direct_api_call_module.direct_api_call(
            chain_id="1",
            endpoint_path="/api/v2/foo?apikey=SECRET",
            ctx=mock_ctx,
        )

    # Primary guard: no beats, no logs
    assert mock_ctx.report_progress.await_count == 0
    assert mock_ctx.info.await_count == 0

    # Secondary guard: no message containing '?' or the secret token was recorded
    for call in mock_ctx.report_progress.await_args_list:
        msg = call.kwargs.get("message", "")
        assert "?" not in msg, f"'?' found in progress message: {msg!r}"
        assert "SECRET" not in msg, f"Secret token found in progress message: {msg!r}"

    for call in mock_ctx.info.await_args_list:
        # ctx.info is called with a positional string argument
        args = call.args
        msg = args[0] if args else ""
        assert "?" not in msg, f"'?' found in info log: {msg!r}"
        assert "SECRET" not in msg, f"Secret token found in info log: {msg!r}"
