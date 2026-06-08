# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the low-credits advisory note emitted by build_tool_response.

Covers threshold boundary behavior, zero/negative balances, the non-finite
header regression guard, the disabled-threshold and no-sink cases,
coexistence with caller-supplied notes and pagination instructions, and
integer display formatting.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import CreditSink, _credit_sink


@contextmanager
def _set_sink(sink: CreditSink | None):
    """Context manager that sets _credit_sink and resets it in finally."""
    token = _credit_sink.set(sink)
    try:
        yield
    finally:
        _credit_sink.reset(token)


class _MockResponse:
    """Minimal fake httpx response for GET/POST helpers."""

    def __init__(self, json_data=None, status_code=200, headers=None):
        self._json_data = json_data
        self.status_code = status_code
        self.reason_phrase = "OK"
        self.request = httpx.Request("GET", "https://api.blockscout.com/1/x")
        self.text = ""
        self.headers = headers if headers is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=self)

    def json(self):
        return self._json_data


def test_build_tool_response_note_present_below_threshold():
    """Advisory note appears when the sink's remaining value is below the threshold."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(4999.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert len(response.notes) == 1
    assert "4999" in response.notes[0]
    assert "5000" in response.notes[0]
    assert "https://dev.blockscout.com" in response.notes[0]


def test_build_tool_response_note_absent_at_threshold():
    """No advisory note when remaining equals the threshold (not strictly below)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(5000.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_absent_above_threshold():
    """No advisory note when remaining is well above the threshold."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(9000.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_present_for_zero_balance():
    """Advisory note appears when remaining is exactly zero."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(0.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert len(response.notes) == 1
    assert "0" in response.notes[0]


def test_build_tool_response_note_present_for_negative_balance():
    """Advisory note appears when remaining is negative (overdrawn paid account)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(-50.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert len(response.notes) == 1
    assert "-50" in response.notes[0]


@pytest.mark.parametrize("header_value", ["-Infinity", "-inf", "nan", "Infinity"])
def test_build_tool_response_no_crash_on_non_finite_captured_header(header_value):
    """End-to-end regression: a non-finite ``x-credits-remaining`` header must
    not crash ``build_tool_response`` and must not emit an advisory note.

    ``float("-Infinity")`` previously reached ``int(remaining)`` in the display
    branch and raised ``OverflowError``.  With the finite guard in
    ``CreditSink.record`` the value never enters the sink, so ``remaining``
    stays ``None`` and no note is produced.
    """
    from blockscout_mcp_server.tools.common import _capture_credits_remaining, build_tool_response

    sink = CreditSink()
    with _set_sink(sink):
        _capture_credits_remaining(_MockResponse(headers={"x-credits-remaining": header_value}))
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert sink.remaining is None
    assert response.notes is None


def test_build_tool_response_note_absent_when_threshold_disabled():
    """No advisory note when threshold is 0 (feature disabled), even with a low balance."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(100.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 0):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_absent_when_no_sink():
    """No advisory note when there is no sink in context (_credit_sink is None)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    # _credit_sink defaults to None — do not set a sink
    assert _credit_sink.get() is None
    response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_absent_when_sink_has_no_value():
    """No advisory note when a sink exists but never captured a value (remaining is None)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    # Do not call sink.record() — remaining stays None

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_coexists_with_caller_notes():
    """Advisory note is appended to caller-supplied notes without mutating the original list."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(100.0)

    original_notes = ["existing note"]

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True}, notes=original_notes)

    # Original list must not be mutated
    assert original_notes == ["existing note"]

    assert response.notes is not None
    assert len(response.notes) == 2
    assert response.notes[0] == "existing note"
    assert "https://dev.blockscout.com" in response.notes[1]


def test_build_tool_response_note_coexists_with_pagination_instructions():
    """Advisory note in notes does not disturb auto-appended pagination instructions."""
    from blockscout_mcp_server.models import NextCallInfo, PaginationInfo
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(1000.0)

    pagination = PaginationInfo(
        next_call=NextCallInfo(tool_name="get_block_info", params={"chain_id": "1", "cursor": "abc"})
    )

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True}, pagination=pagination)

    # Advisory note must appear in notes
    assert response.notes is not None
    assert any("https://dev.blockscout.com" in n for n in response.notes)

    # Pagination instructions must be present
    assert response.instructions is not None
    assert any("MORE DATA AVAILABLE" in i for i in response.instructions)


def test_build_tool_response_integer_display_for_whole_number():
    """Remaining balance is displayed as an integer (4999, not 4999.0) when it is whole."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(4999.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    note = response.notes[0]
    assert "4999 credits" in note
    assert "4999.0" not in note
