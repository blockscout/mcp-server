# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the PRO-API-key-required notice (issue #425).

Phase 2 covers only ``client_supplied_valid_key()`` — the helper that reports
whether the current request's effective credential is a client-supplied PRO
API key, so response assembly (Phase 3) never has to touch this module's
private state classes directly. Phase 3 extends this file with the
notice-assembly tests (gating, ordering, non-mutation in ``build_tool_response``)
plus the decorator-seam tests proving the whole chain — decorator -> ContextVar
-> helper -> response — integrates. Keep the whole file under 500 LOC per
rule 210.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from pro_api_key_helpers import ctx_with_header

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import NextCallInfo, PaginationInfo
from blockscout_mcp_server.pro_api_key_context import (
    CreditSink,
    _Absent,
    _client_key_state,
    _credit_sink,
    _Malformed,
    _Valid,
    client_supplied_valid_key,
    pro_api_key_scope,
)
from blockscout_mcp_server.tools.common import build_tool_response


@contextmanager
def _set_client_key_state(state):
    """Context manager that sets _client_key_state and resets it in finally."""
    token = _client_key_state.set(state)
    try:
        yield
    finally:
        _client_key_state.reset(token)


# ===========================================================================
# client_supplied_valid_key() — mapping from every ContextVar state to bool
# ===========================================================================


def test_valid_client_key_state_returns_true():
    with _set_client_key_state(_Valid(value="client-key-123")):
        assert client_supplied_valid_key() is True


def test_absent_state_returns_false():
    with _set_client_key_state(_Absent()):
        assert client_supplied_valid_key() is False


def test_malformed_state_returns_false():
    with _set_client_key_state(_Malformed()):
        assert client_supplied_valid_key() is False


def test_no_state_set_returns_false():
    """Outside any @pro_api_key_scope, the ContextVar reads its _ABSENT default."""
    assert client_supplied_valid_key() is False


# ===========================================================================
# build_tool_response notice assembly — gating, ordering, non-mutation
# ===========================================================================

_NOTICE_TEXT = "PRO API keys will soon be required for every request; see https://dev.blockscout.com."


def test_notice_present_and_last_when_state_absent(monkeypatch):
    """Notice configured, state _Absent -> notice present and last entry."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    with _set_client_key_state(_Absent()):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == _NOTICE_TEXT


def test_notice_present_when_state_malformed(monkeypatch):
    """Notice configured, state _Malformed -> notice present (malformed key is not usable)."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    with _set_client_key_state(_Malformed()):
        response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == _NOTICE_TEXT


def test_notice_present_when_no_state_set(monkeypatch):
    """Notice configured, no state set (ContextVar default) -> notice present."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert response.notes[-1] == _NOTICE_TEXT


def test_notice_absent_when_state_valid(monkeypatch):
    """Notice configured, state _Valid -> notes unchanged (no notice)."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    with _set_client_key_state(_Valid(value="client-key-123")):
        response = build_tool_response(data={"ok": True})

    assert response.notes is None


@pytest.mark.parametrize("state", [_Absent(), _Malformed(), _Valid(value="client-key-123")])
def test_no_notice_for_any_state_when_notice_empty(state, monkeypatch):
    """Notice empty -> no notice for any state, notes stays None.

    Set the empty notice explicitly rather than asserting the global default, so
    the test stays hermetic even when a developer's environment/.env defines
    ``BLOCKSCOUT_PRO_API_KEY_REQUIRED_NOTICE``.
    """
    monkeypatch.setattr(config, "pro_api_key_required_notice", "")

    with _set_client_key_state(state):
        response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_notice_ordering_with_low_credits_advisory(monkeypatch):
    """Both the low-credits advisory and the key-requirement notice can fire together;
    the advisory comes first and the key-requirement notice is appended last."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)
    monkeypatch.setattr(config, "pro_api_low_credits_threshold", 5000)

    sink = CreditSink()
    sink.record(4999.0)
    token = _credit_sink.set(sink)
    try:
        with _set_client_key_state(_Absent()):
            response = build_tool_response(data={"ok": True})
    finally:
        _credit_sink.reset(token)

    assert response.notes is not None
    assert len(response.notes) == 2
    assert "4999" in response.notes[0]
    assert response.notes[1] == _NOTICE_TEXT


def test_notice_preserves_caller_notes_without_mutation(monkeypatch):
    """Caller-supplied notes are preserved in order before the notice, and the
    caller's original list object is not mutated."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    original_notes = ["existing note"]

    with _set_client_key_state(_Absent()):
        response = build_tool_response(data={"ok": True}, notes=original_notes)

    # Original list must not be mutated
    assert original_notes == ["existing note"]

    assert response.notes is not None
    assert response.notes == ["existing note", _NOTICE_TEXT]


def test_notice_coexists_with_pagination_instructions(monkeypatch):
    """instructions/pagination output is identical to today's behavior; the
    notice only affects notes."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)

    pagination = PaginationInfo(
        next_call=NextCallInfo(tool_name="get_block_info", params={"chain_id": "1", "cursor": "abc"})
    )

    with _set_client_key_state(_Absent()):
        response = build_tool_response(data={"ok": True}, pagination=pagination)

    assert response.notes is not None
    assert response.notes[-1] == _NOTICE_TEXT

    assert response.instructions is not None
    assert any("MORE DATA AVAILABLE" in i for i in response.instructions)
    assert response.pagination == pagination


# ===========================================================================
# Decorator-seam tests — decorator -> ContextVar -> helper -> response
# ===========================================================================


@pro_api_key_scope
async def _probe_tool(ctx):
    """Minimal tool-shaped function proving the full integration chain."""
    return build_tool_response(data={"ok": True})


@pytest.mark.asyncio
async def test_decorator_seam_well_formed_client_key_suppresses_notice(monkeypatch):
    """A context carrying a well-formed key under the configured header ->
    the decorator resolves a _Valid state and the notice is suppressed."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    ctx = ctx_with_header(config.pro_api_key_header, "client-key-456")
    response = await _probe_tool(ctx)

    assert response.notes is None


@pytest.mark.asyncio
async def test_decorator_seam_http_context_without_key_header_shows_notice(monkeypatch):
    """An HTTP-shaped context whose headers do not include the configured key
    header -> the decorator resolves _Absent and the notice is present."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    ctx = ctx_with_header("X-Some-Unrelated-Header", "irrelevant-value")
    response = await _probe_tool(ctx)

    assert response.notes is not None
    assert response.notes[-1] == _NOTICE_TEXT


@pytest.mark.asyncio
async def test_decorator_seam_stdio_context_shows_notice(monkeypatch):
    """A stdio-shaped context (no request_context) -> the decorator resolves
    _Absent and the notice is present."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", _NOTICE_TEXT)
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    ctx = SimpleNamespace(request_context=None)
    response = await _probe_tool(ctx)

    assert response.notes is not None
    assert response.notes[-1] == _NOTICE_TEXT
