# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests proving `log_tool_invocation` redacts a live `session_id` value before it
reaches any observability sink (issue #442, Phase 7).

Split out from `tests/tools/test_decorators.py` (already at 419 lines, close to the
500-line test-file guideline) to keep both files under the limit. Exercises only the
redaction behavior added in `blockscout_mcp_server/tools/decorators.py`; the rest of
`log_tool_invocation`'s behavior (client-meta extraction, auth-signal threading, etc.)
is already covered there.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import Context

from blockscout_mcp_server.config import config as server_config
from blockscout_mcp_server.tools.decorators import log_tool_invocation

RAW_SESSION_ID = "abc123.1700000000.deadbeefcafebabe"
PLACEHOLDER = "<redacted>"


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.tools.decorators.telemetry.send_community_usage_report",
    new_callable=AsyncMock,
)
async def test_session_id_redacted_from_all_sinks_on_success(
    mock_report, monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx: Context
) -> None:
    """A present, non-empty `session_id` is masked in the log line, in the arguments
    handed to `analytics.track_tool_invocation`, and in the payload handed to
    `telemetry.send_community_usage_report` — never the raw value in any of them."""
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")
    monkeypatch.setattr(server_config, "disable_community_telemetry", False, raising=False)

    analytics_calls = {}

    def fake_track(ctx, name, args, client_meta=None, auth_origin=None, api_key_fingerprint=None):  # type: ignore[no-untyped-def]
        analytics_calls["args"] = dict(args)

    monkeypatch.setattr("blockscout_mcp_server.tools.decorators.analytics.track_tool_invocation", fake_track)

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context, session_id: str | None = None) -> int:
        return a

    mock_ctx.session = None
    mock_ctx.request_context = None

    result = await dummy_tool(7, ctx=mock_ctx, session_id=RAW_SESSION_ID)
    await asyncio.sleep(0)

    assert result == 7

    # 1. The INFO log line never contains the raw value, only the placeholder.
    log_text = caplog.text
    assert RAW_SESSION_ID not in log_text
    assert PLACEHOLDER in log_text

    # 2. The arguments handed to analytics.track_tool_invocation never contain the raw value.
    assert analytics_calls["args"]["session_id"] == PLACEHOLDER

    # 3. The payload handed to telemetry.send_community_usage_report never contains the raw value.
    mock_report.assert_awaited_once()
    call_args = mock_report.await_args.args
    tool_args_payload = call_args[1]
    assert tool_args_payload["session_id"] == PLACEHOLDER
    assert RAW_SESSION_ID not in str(mock_report.await_args)


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.tools.decorators.telemetry.send_community_usage_report",
    new_callable=AsyncMock,
)
async def test_session_id_redacted_from_all_sinks_when_tool_raises(
    mock_report, monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx: Context
) -> None:
    """Telemetry fires in a `finally` block, so a refusal (the wrapped function raising)
    must still mask the identifier in every sink."""
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")
    monkeypatch.setattr(server_config, "disable_community_telemetry", False, raising=False)

    analytics_calls = {}

    def fake_track(ctx, name, args, client_meta=None, auth_origin=None, api_key_fingerprint=None):  # type: ignore[no-untyped-def]
        analytics_calls["args"] = dict(args)

    monkeypatch.setattr("blockscout_mcp_server.tools.decorators.analytics.track_tool_invocation", fake_track)

    @log_tool_invocation
    async def failing_tool(ctx: Context, session_id: str | None = None) -> None:
        raise RuntimeError("boom")

    mock_ctx.session = None
    mock_ctx.request_context = None

    with pytest.raises(RuntimeError, match="boom"):
        await failing_tool(ctx=mock_ctx, session_id=RAW_SESSION_ID)
    await asyncio.sleep(0)

    log_text = caplog.text
    assert RAW_SESSION_ID not in log_text
    assert PLACEHOLDER in log_text

    assert analytics_calls["args"]["session_id"] == PLACEHOLDER

    mock_report.assert_awaited_once()
    call_args = mock_report.await_args.args
    tool_args_payload = call_args[1]
    assert tool_args_payload["session_id"] == PLACEHOLDER
    assert RAW_SESSION_ID not in str(mock_report.await_args)


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.tools.decorators.telemetry.send_community_usage_report",
    new_callable=AsyncMock,
)
async def test_no_session_id_argument_leaves_output_unchanged(
    mock_report, monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx: Context
) -> None:
    """A call without `session_id` (today's ungated behavior) is not touched by the masking:
    no placeholder is injected, and the argument dict is unchanged from before this feature."""
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")
    monkeypatch.setattr(server_config, "disable_community_telemetry", False, raising=False)

    analytics_calls = {}

    def fake_track(ctx, name, args, client_meta=None, auth_origin=None, api_key_fingerprint=None):  # type: ignore[no-untyped-def]
        analytics_calls["args"] = dict(args)

    monkeypatch.setattr("blockscout_mcp_server.tools.decorators.analytics.track_tool_invocation", fake_track)

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    mock_ctx.session = None
    mock_ctx.request_context = None

    result = await dummy_tool(7, ctx=mock_ctx)
    await asyncio.sleep(0)

    assert result == 7
    assert PLACEHOLDER not in caplog.text
    assert analytics_calls["args"] == {"a": 7}

    mock_report.assert_awaited_once()
    call_args = mock_report.await_args.args
    tool_args_payload = call_args[1]
    assert tool_args_payload == {"a": 7}
