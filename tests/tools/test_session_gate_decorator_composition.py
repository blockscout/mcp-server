# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for @session_gate / @session_gate_unmetered composition (Issue #442, Phase 4).

Split out of `tests/tools/test_session_gate_decorator.py` (which covers the core
disabled/exempt/missing/invalid/expired/happy-path/exhaustion/refund/cancellation/
store-fault/database-replacement branches) to keep both files under the ~500 LOC
guideline. This file covers: pagination continuation injection, the
`@session_gate_unmetered` variant (`get_chains_list`'s decorator), the mandated
decorator stacking order, the malformed-client-key precedence contract, and the
sweep-vs-token invariant.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.pro_api_key_context import (
    CreditSink,
    pro_api_credit_scope,
    pro_api_key_scope,
)
from blockscout_mcp_server.session_gate import (
    SessionBudgetExhaustedError,
    SessionExpiredError,
    SessionIdMissingError,
    SessionStoreUnavailableError,
    get_effective_max_calls,
    get_remaining_budget,
    mint_token,
    session_gate,
    session_gate_unmetered,
    verify_token,
)
from blockscout_mcp_server.session_store import get_store
from tests.pro_api_key_helpers import ctx_with_header, ctx_with_malformed_header


@pytest.fixture
def store_spy(enabled_session_gate, monkeypatch):
    """Wrap the real, already-initialized store in a spy so tests can assert which
    of its methods were (or were not) invoked, without losing real SQL behavior."""
    real_store = get_store()
    spy = MagicMock(wraps=real_store)
    monkeypatch.setattr("blockscout_mcp_server.session_gate.get_store", lambda: spy)
    return spy


def _minted() -> tuple[str, str, int]:
    """Mint a token and return (token, random_part, issued_at)."""
    token = mint_token()
    random_part, issued_at = verify_token(token)
    return token, random_part, issued_at


# ---------------------------------------------------------------------------
# Pagination injection
# ---------------------------------------------------------------------------


def _paginated_response() -> ToolResponse:
    return ToolResponse(
        data={"x": 1},
        pagination=PaginationInfo(next_call=NextCallInfo(tool_name="dummy_tool", params={"cursor": "abc"})),
    )


@pytest.mark.asyncio
async def test_pagination_injection_metered(enabled_session_gate, mock_ctx):
    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return _paginated_response()

    result = await tool(ctx=mock_ctx, session_id=token)

    assert result.pagination.next_call.params == {"cursor": "abc", "session_id": token}


@pytest.mark.asyncio
async def test_pagination_injection_unmetered(enabled_session_gate, mock_ctx):
    token, _random_part, _issued_at = _minted()

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        return _paginated_response()

    result = await tool(ctx=mock_ctx, session_id=token)

    assert result.pagination.next_call.params == {"cursor": "abc", "session_id": token}


@pytest.mark.asyncio
async def test_no_pagination_response_returned_unmodified(enabled_session_gate, mock_ctx):
    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return ToolResponse(data={"x": 1})

    result = await tool(ctx=mock_ctx, session_id=token)

    assert result.pagination is None


@pytest.mark.asyncio
async def test_disabled_path_never_injects(mock_ctx):
    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return _paginated_response()

    result = await tool(ctx=mock_ctx)
    assert result.pagination.next_call.params == {"cursor": "abc"}


@pytest.mark.asyncio
async def test_exempt_path_never_injects(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr("blockscout_mcp_server.session_gate.client_supplied_valid_key", lambda: True)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return _paginated_response()

    result = await tool(ctx=mock_ctx)
    assert result.pagination.next_call.params == {"cursor": "abc"}


# ---------------------------------------------------------------------------
# Unmetered variant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unmetered_valid_token_reads_but_never_increments(enabled_session_gate, store_spy, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 7)
    token, random_part, _issued_at = _minted()

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        return get_remaining_budget()

    remaining = await tool(ctx=mock_ctx, session_id=token)

    assert remaining == 7
    store_spy.get_calls.assert_called_once_with(random_part)
    store_spy.check_and_increment.assert_not_called()
    assert get_store().get_calls(random_part) == 0  # no row created
    assert get_remaining_budget() is None  # reset after the call
    assert get_effective_max_calls() is None  # reset after the call


@pytest.mark.asyncio
async def test_unmetered_store_fault_on_read_raises_unavailable(enabled_session_gate, monkeypatch, mock_ctx):
    token, _random_part, _issued_at = _minted()

    store = get_store()
    monkeypatch.setattr(store, "get_calls", MagicMock(side_effect=RuntimeError("disk full")))

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionStoreUnavailableError):
        await tool(ctx=mock_ctx, session_id=token)


@pytest.mark.asyncio
async def test_unmetered_expired_token_raises_expired(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()
    monkeypatch.setattr(time, "time", lambda: now + 101)

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionExpiredError):
        await tool(ctx=mock_ctx, session_id=token)


@pytest.mark.asyncio
async def test_unmetered_exhausted_but_unexpired_identifier_reports_zero(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 1)
    token, random_part, issued_at = _minted()
    store = get_store()
    store.check_and_increment(random_part, issued_at, config.session_mcp_max_calls)  # spend the only unit

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        return get_remaining_budget()

    remaining = await tool(ctx=mock_ctx, session_id=token)

    assert remaining == 0


@pytest.mark.asyncio
async def test_unmetered_floors_at_zero_when_max_calls_lowered(enabled_session_gate, monkeypatch, mock_ctx):
    token, random_part, issued_at = _minted()
    store = get_store()
    for _ in range(3):
        store.check_and_increment(random_part, issued_at, max_calls=100)

    monkeypatch.setattr(config, "session_mcp_max_calls", 1)  # lowered below the recorded count

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        return get_remaining_budget()

    remaining = await tool(ctx=mock_ctx, session_id=token)

    assert remaining == 0


# ---------------------------------------------------------------------------
# Terminal-text equality
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expiry_and_exhaustion_errors_share_identical_message(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 1)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token, random_part, issued_at = _minted()
    get_store().check_and_increment(random_part, issued_at, config.session_mcp_max_calls)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionBudgetExhaustedError) as exhausted_info:
        await tool(ctx=mock_ctx, session_id=token)

    monkeypatch.setattr(config, "session_ttl_seconds", 1)
    monkeypatch.setattr(time, "time", lambda: now + 1000)
    with pytest.raises(SessionExpiredError) as expired_info:
        await tool(ctx=mock_ctx, session_id=token)

    assert str(exhausted_info.value) == str(expired_info.value)


# ---------------------------------------------------------------------------
# Stacking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stacking_under_pro_api_key_scope_with_client_key_exempts(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    calls = {"n": 0}

    @pro_api_key_scope
    @session_gate
    async def tool(ctx, session_id: str | None = None):
        calls["n"] += 1
        return "ok"

    ctx = ctx_with_header(config.pro_api_key_header, "a-client-key")
    result = await tool(ctx=ctx)

    assert result == "ok"
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_stacking_without_pro_api_key_scope_gates_even_with_key_present(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    # The same ctx that would exempt the caller under @pro_api_key_scope is
    # gated when that scope is absent — client_supplied_valid_key() reads a
    # ContextVar only @pro_api_key_scope populates.
    ctx = ctx_with_header(config.pro_api_key_header, "a-client-key")
    with pytest.raises(SessionIdMissingError):
        await tool(ctx=ctx)


@pytest.mark.asyncio
async def test_full_production_order(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    sinks_created: list[CreditSink] = []
    real_credit_sink_cls = CreditSink

    class SpyCreditSink(real_credit_sink_cls):
        def __init__(self) -> None:
            super().__init__()
            sinks_created.append(self)

    monkeypatch.setattr("blockscout_mcp_server.pro_api_key_context.CreditSink", SpyCreditSink)

    body_entered = {"n": 0}
    observed_budget = {}

    @pro_api_key_scope
    @session_gate
    @pro_api_credit_scope
    async def tool(ctx, session_id: str | None = None, fail: bool = False):
        body_entered["n"] += 1
        observed_budget["value"] = get_remaining_budget()
        if fail:
            raise ValueError("body failure")
        return "ok"

    # 1. Exempt call: passes through, no store access, credit sink still created
    #    (pro_api_credit_scope is transport-agnostic and always establishes a sink).
    exempt_ctx = ctx_with_header(config.pro_api_key_header, "a-client-key")
    result = await tool(ctx=exempt_ctx)
    assert result == "ok"
    assert body_entered["n"] == 1
    assert len(sinks_created) == 1

    # 2. A gate refusal (missing session_id, no client key) never enters the credit scope.
    sinks_created.clear()
    body_entered["n"] = 0
    plain_ctx = ctx_with_header("X-Unrelated", "value")
    with pytest.raises(SessionIdMissingError):
        await tool(ctx=plain_ctx)
    assert body_entered["n"] == 0
    assert sinks_created == []

    # 3. A successful gated call sets the budget ContextVar and the credit scope behaves normally.
    token, _random_part, _issued_at = _minted()
    result = await tool(ctx=plain_ctx, session_id=token)
    assert result == "ok"
    assert observed_budget["value"] == config.session_mcp_max_calls - 1
    assert len(sinks_created) == 1
    assert get_remaining_budget() is None  # reset afterwards
    assert get_effective_max_calls() is None  # reset afterwards

    # 4. A failing body refunds and both ContextVars are reset afterwards.
    store = get_store()
    _random_part2, issued_at2 = verify_token(token)
    before = store.get_calls(_random_part2)
    with pytest.raises(ValueError, match="body failure"):
        await tool(ctx=plain_ctx, session_id=token, fail=True)
    assert store.get_calls(_random_part2) == before
    assert get_remaining_budget() is None
    assert get_effective_max_calls() is None


# ---------------------------------------------------------------------------
# Malformed-key precedence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_key_never_exempts_missing_session_id_wins(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    @pro_api_key_scope
    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    malformed_ctx = ctx_with_malformed_header(config.pro_api_key_header, "x" * 300)
    with pytest.raises(SessionIdMissingError):
        await tool(ctx=malformed_ctx)


@pytest.mark.asyncio
async def test_malformed_key_with_valid_token_propagates_key_error_and_refunds(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    token, random_part, _issued_at = _minted()
    store = get_store()
    before = store.get_calls(random_part)

    @pro_api_key_scope
    @session_gate
    async def tool(ctx, session_id: str | None = None):
        # Simulates a downstream PRO API chokepoint raising for a malformed key.
        raise ValueError("malformed key error")

    malformed_ctx = ctx_with_malformed_header(config.pro_api_key_header, "x" * 300)
    with pytest.raises(ValueError, match="malformed key error"):
        await tool(ctx=malformed_ctx, session_id=token)

    assert store.get_calls(random_part) == before


# ---------------------------------------------------------------------------
# Sweep-vs-token invariant
# ---------------------------------------------------------------------------


def test_sweep_vs_token_invariant(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()
    random_part, issued_at = verify_token(token)
    store = get_store()
    store.check_and_increment(random_part, issued_at, max_calls=100)

    # Advance past the TTL: the token is rejected...
    monkeypatch.setattr(time, "time", lambda: now + 101)
    with pytest.raises(SessionExpiredError):
        verify_token(token)

    # ...even though the row is, by construction, sweep-eligible.
    deleted = store.sweep_batch(100)
    assert deleted == 1


def test_swept_then_revived_identifier_restarts_counter(enabled_session_gate, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 1000)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()
    random_part, issued_at = verify_token(token)
    store = get_store()
    store.check_and_increment(random_part, issued_at, max_calls=100)
    store.check_and_increment(random_part, issued_at, max_calls=100)  # partially spent (calls=2)

    # Lower the TTL so the row becomes sweep-eligible, then sweep it away.
    monkeypatch.setattr(config, "session_ttl_seconds", 10)
    monkeypatch.setattr(time, "time", lambda: now + 20)
    deleted = store.sweep_batch(100)
    assert deleted == 1
    assert store.get_calls(random_part) == 0

    # Raise the TTL past the token's age: the same token verifies again.
    monkeypatch.setattr(config, "session_ttl_seconds", 1000)
    random_part2, issued_at2 = verify_token(token)
    assert random_part2 == random_part

    # The next metered call recreates the row with calls = 1 (a fresh budget).
    calls = store.check_and_increment(random_part2, issued_at2, max_calls=100)
    assert calls == 1
