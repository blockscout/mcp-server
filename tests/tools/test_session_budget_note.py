# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the session-budget response note (issue #442, Phase 5).

Covers only `build_tool_response`'s note-assembly branch driven by
`session_gate.get_remaining_budget()`. The decorator seam that actually sets the
ContextVar over the real MCP transport is covered by
`tests/test_session_gate_http_transport.py`.
"""

from __future__ import annotations

from contextlib import contextmanager

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SESSION_BUDGET_NOTE_TEMPLATE
from blockscout_mcp_server.pro_api_key_context import CreditSink, _credit_sink
from blockscout_mcp_server.session_gate import _remaining_budget
from blockscout_mcp_server.tools.common import build_tool_response

_NOTICE_TEXT = "PRO API keys will soon be required for every request; see https://dev.blockscout.com."


@contextmanager
def _set_remaining_budget(value):
    """Context manager that sets the session-gate ContextVar and resets it in finally."""
    token = _remaining_budget.set(value)
    try:
        yield
    finally:
        _remaining_budget.reset(token)


def test_note_appended_when_remaining_budget_set(monkeypatch):
    """ContextVar set to a value -> note appended, formatted with that value and
    the non-default configured session_max_calls."""
    monkeypatch.setattr(config, "session_max_calls", 7)

    with _set_remaining_budget(3):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=3, max_calls=7)


def test_no_note_when_context_var_unset():
    """ContextVar unset (default) -> no note; caller-supplied notes pass through
    unchanged (including None staying None)."""
    response = build_tool_response(data={"ok": True})
    assert response.notes is None

    original_notes = ["existing note"]
    response_with_notes = build_tool_response(data={"ok": True}, notes=original_notes)
    assert response_with_notes.notes == ["existing note"]
    assert original_notes == ["existing note"]


def test_note_present_and_correct_when_remaining_is_zero(monkeypatch):
    """remaining == 0 -> note present and reads '0 of N'."""
    monkeypatch.setattr(config, "session_max_calls", 5)

    with _set_remaining_budget(0):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=0, max_calls=5)
    assert "0 of 5 tool calls remaining" in response.notes[-1]


def test_note_ordering_with_low_credits_and_operator_notice(monkeypatch):
    """With the low-credits sink populated, the ContextVar set, and
    pro_api_key_required_notice configured, notes appear in the order
    caller-notes -> low-credits -> budget -> operator notice."""
    monkeypatch.setattr(config, "pro_api_low_credits_threshold", 5000)
    monkeypatch.setattr(config, "session_max_calls", 5)
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    sink = CreditSink()
    sink.record(4999.0)
    sink_token = _credit_sink.set(sink)
    try:
        with _set_remaining_budget(2):
            response = build_tool_response(data={"ok": True}, notes=["caller note"])
    finally:
        _credit_sink.reset(sink_token)

    assert response.notes is not None
    assert len(response.notes) == 4
    assert response.notes[0] == "caller note"
    assert "4999" in response.notes[1]
    assert response.notes[2] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=2, max_calls=5)
    assert response.notes[3] == _NOTICE_TEXT


def test_caller_notes_list_not_mutated_in_place(monkeypatch):
    """Caller-supplied notes list is never mutated in place."""
    monkeypatch.setattr(config, "session_max_calls", 5)

    original_notes = ["existing note"]
    with _set_remaining_budget(1):
        response = build_tool_response(data={"ok": True}, notes=original_notes)

    assert original_notes == ["existing note"]
    assert response.notes == ["existing note", SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=1, max_calls=5)]
