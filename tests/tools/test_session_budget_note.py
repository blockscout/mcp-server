# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the session-budget response note (issue #442, Phase 5).

Covers only `build_tool_response`'s note-assembly branch driven by
`session_gate.get_remaining_budget()` / `session_gate.get_effective_max_calls()`. The
decorator seam that actually sets both ContextVars over the real MCP transport is
covered by `tests/test_session_gate_http_transport.py`.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SESSION_BUDGET_NOTE_TEMPLATE
from blockscout_mcp_server.pro_api_key_context import CreditSink, _credit_sink
from blockscout_mcp_server.session_gate import _effective_max_calls, _remaining_budget
from blockscout_mcp_server.tools.common import build_tool_response

_NOTICE_TEXT = "PRO API keys will soon be required for every request; see https://dev.blockscout.com."


@contextmanager
def _set_remaining_budget(remaining, max_calls=None):
    """Context manager that sets the session-gate ContextVars and resets them in finally.

    ``max_calls=None`` (the default) sets ``_effective_max_calls`` to ``None``
    explicitly — never inheriting an ambient value — which exercises the defensive
    branch in `build_tool_response` where `remaining` is set but the effective
    ceiling is not.
    """
    remaining_token = _remaining_budget.set(remaining)
    max_calls_token = _effective_max_calls.set(max_calls)
    try:
        yield
    finally:
        _remaining_budget.reset(remaining_token)
        _effective_max_calls.reset(max_calls_token)


def test_note_appended_when_remaining_budget_set():
    """Both ContextVars set -> note appended, formatted with those values."""
    with _set_remaining_budget(3, max_calls=7):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=3, max_calls=7)


def test_note_reads_effective_ceiling_not_config(monkeypatch):
    """Effective ceiling ContextVar differs from the config MCP default -> the note
    shows the ContextVar value, proving config is no longer consulted."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)

    with _set_remaining_budget(1, max_calls=3):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=1, max_calls=3)
    assert "of 3 tool calls remaining" in response.notes[-1]


def test_no_note_when_context_var_unset():
    """ContextVar unset (default) -> no note; caller-supplied notes pass through
    unchanged (including None staying None)."""
    response = build_tool_response(data={"ok": True})
    assert response.notes is None

    original_notes = ["existing note"]
    response_with_notes = build_tool_response(data={"ok": True}, notes=original_notes)
    assert response_with_notes.notes == ["existing note"]
    assert original_notes == ["existing note"]


def test_note_present_and_correct_when_remaining_is_zero():
    """remaining == 0 -> note present and reads '0 of N'."""
    with _set_remaining_budget(0, max_calls=5):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=0, max_calls=5)
    assert "0 of 5 tool calls remaining" in response.notes[-1]


def test_no_note_and_error_logged_when_effective_ceiling_unset(caplog):
    """Defensive branch: remaining is set but the effective ceiling is not -> no
    session-budget note is emitted, the response is otherwise assembled normally,
    and an ERROR-level record names the broken invariant."""
    with caplog.at_level(logging.ERROR, logger="blockscout_mcp_server.tools.common"):
        with _set_remaining_budget(2):
            response = build_tool_response(data={"ok": True}, notes=["caller note"])

    assert response.notes == ["caller note"]
    assert not any("Free session budget" in note for note in response.notes)
    error_records = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert error_records
    assert any(
        "pairing invariant" in record.message and "effective max_calls is None" in record.message
        for record in error_records
    )


def test_note_ordering_with_low_credits_and_operator_notice(monkeypatch):
    """With the low-credits sink populated, both ContextVars set, and
    pro_api_key_required_notice configured, notes appear in the order
    caller-notes -> low-credits -> budget -> operator notice."""
    monkeypatch.setattr(config, "pro_api_low_credits_threshold", 5000)
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    sink = CreditSink()
    sink.record(4999.0)
    sink_token = _credit_sink.set(sink)
    try:
        with _set_remaining_budget(2, max_calls=5):
            response = build_tool_response(data={"ok": True}, notes=["caller note"])
    finally:
        _credit_sink.reset(sink_token)

    assert response.notes is not None
    assert len(response.notes) == 4
    assert response.notes[0] == "caller note"
    assert "4999" in response.notes[1]
    assert response.notes[2] == SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=2, max_calls=5)
    assert response.notes[3] == _NOTICE_TEXT


def test_caller_notes_list_not_mutated_in_place():
    """Caller-supplied notes list is never mutated in place."""
    original_notes = ["existing note"]
    with _set_remaining_budget(1, max_calls=5):
        response = build_tool_response(data={"ok": True}, notes=original_notes)

    assert original_notes == ["existing note"]
    assert response.notes == ["existing note", SESSION_BUDGET_NOTE_TEMPLATE.format(remaining=1, max_calls=5)]
