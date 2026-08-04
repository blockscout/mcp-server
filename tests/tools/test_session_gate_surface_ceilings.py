# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for per-surface ceilings and zero-ceiling policy (Issue #446, Phase 4).

Covers surface resolution (`analytics.get_call_source(ctx) == "rest"` selects
`config.session_rest_max_calls`, anything else selects `config.session_mcp_max_calls`)
and the zero-ceiling short-circuit position in `@session_gate` / `@session_gate_unmetered`.

Sits in a module of its own: `test_session_gate_decorator.py` and
`test_session_gate_decorator_composition.py` sit near 370 and 437 lines and were
themselves split once already to stay under rule 210's ~500-LOC cap, so this suite
fits neither of them.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SESSION_OVER_MESSAGE
from blockscout_mcp_server.session_gate import (
    SessionBudgetExhaustedError,
    get_effective_max_calls,
    get_remaining_budget,
    mint_token,
    session_gate,
    session_gate_unmetered,
    verify_token,
)
from blockscout_mcp_server.session_store import get_store


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
# Surface resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rest_marked_ctx_charges_against_rest_ceiling(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 1)
    mock_ctx.call_source = "rest"
    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    # First call consumes the single unit of REST budget.
    await tool(ctx=mock_ctx, session_id=token)

    # Second call is refused at the REST ceiling, not the (higher) MCP one.
    with pytest.raises(SessionBudgetExhaustedError):
        await tool(ctx=mock_ctx, session_id=token)


@pytest.mark.asyncio
async def test_unmarked_ctx_charges_against_mcp_ceiling(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 1)
    monkeypatch.setattr(config, "session_rest_max_calls", 5)
    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    await tool(ctx=mock_ctx, session_id=token)

    with pytest.raises(SessionBudgetExhaustedError):
        await tool(ctx=mock_ctx, session_id=token)


@pytest.mark.asyncio
async def test_unexpected_marker_charges_against_mcp_ceiling(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 1)
    monkeypatch.setattr(config, "session_rest_max_calls", 5)
    mock_ctx.call_source = "graphql"
    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    await tool(ctx=mock_ctx, session_id=token)

    with pytest.raises(SessionBudgetExhaustedError):
        await tool(ctx=mock_ctx, session_id=token)


@pytest.mark.asyncio
async def test_unknown_fallback_charges_against_mcp_ceiling(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 1)
    monkeypatch.setattr(config, "session_rest_max_calls", 5)
    monkeypatch.setattr("blockscout_mcp_server.session_gate.analytics.get_call_source", lambda ctx: "unknown")
    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    await tool(ctx=mock_ctx, session_id=token)

    with pytest.raises(SessionBudgetExhaustedError):
        await tool(ctx=mock_ctx, session_id=token)


# ---------------------------------------------------------------------------
# Zero-ceiling short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_ceiling_with_valid_token_raises_before_store_io(
    enabled_session_gate, store_spy, monkeypatch, mock_ctx
):
    monkeypatch.setattr(config, "session_mcp_max_calls", 0)
    token, random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionBudgetExhaustedError) as exc_info:
        await tool(ctx=mock_ctx, session_id=token)

    assert str(exc_info.value) == SESSION_OVER_MESSAGE
    store_spy.check_and_increment.assert_not_called()
    assert get_store().get_calls(random_part) == 0


@pytest.mark.asyncio
async def test_zero_ceiling_with_no_session_id_raises_budget_exhausted(
    enabled_session_gate, store_spy, monkeypatch, mock_ctx
):
    monkeypatch.setattr(config, "session_mcp_max_calls", 0)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionBudgetExhaustedError) as exc_info:
        await tool(ctx=mock_ctx)

    assert str(exc_info.value) == SESSION_OVER_MESSAGE
    store_spy.check_and_increment.assert_not_called()


@pytest.mark.asyncio
async def test_zero_ceiling_with_malformed_session_id_raises_budget_exhausted(
    enabled_session_gate, store_spy, monkeypatch, mock_ctx
):
    monkeypatch.setattr(config, "session_mcp_max_calls", 0)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionBudgetExhaustedError) as exc_info:
        await tool(ctx=mock_ctx, session_id="not-a-real-token")

    assert str(exc_info.value) == SESSION_OVER_MESSAGE
    store_spy.check_and_increment.assert_not_called()
    store_spy.get_calls.assert_not_called()


@pytest.mark.asyncio
async def test_zero_ceiling_exempt_caller_passes_through(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 0)
    monkeypatch.setattr("blockscout_mcp_server.session_gate.client_supplied_valid_key", lambda: True)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    result = await tool(ctx=mock_ctx)

    assert result == "ok"


# ---------------------------------------------------------------------------
# ContextVar pair reflects the effective ceiling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remaining_budget_reflects_effective_rest_ceiling(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 3)
    mock_ctx.call_source = "rest"
    token, _random_part, _issued_at = _minted()

    observed = {}

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        observed["remaining"] = get_remaining_budget()
        observed["max_calls"] = get_effective_max_calls()
        return "ok"

    await tool(ctx=mock_ctx, session_id=token)

    assert observed["remaining"] == config.session_rest_max_calls - 1
    assert observed["max_calls"] == config.session_rest_max_calls


@pytest.mark.asyncio
async def test_unmetered_remaining_is_surface_aware(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 2)
    mock_ctx.call_source = "rest"
    token, _random_part, _issued_at = _minted()

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        return get_remaining_budget()

    remaining = await tool(ctx=mock_ctx, session_id=token)

    assert remaining == 2


@pytest.mark.asyncio
async def test_unmetered_zero_rest_ceiling_still_runs_body(enabled_session_gate, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 0)
    mock_ctx.call_source = "rest"
    token, _random_part, _issued_at = _minted()

    observed = {}

    @session_gate_unmetered
    async def tool(ctx, session_id: str | None = None):
        observed["remaining"] = get_remaining_budget()
        observed["max_calls"] = get_effective_max_calls()
        return "ok"

    result = await tool(ctx=mock_ctx, session_id=token)

    assert result == "ok"
    assert observed["remaining"] == 0
    assert observed["max_calls"] == 0


# ---------------------------------------------------------------------------
# ContextVar restoration and cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contextvars_are_restored_not_cleared(enabled_session_gate, mock_ctx):
    from blockscout_mcp_server.session_gate import _effective_max_calls, _remaining_budget

    remaining_sentinel_token = _remaining_budget.set(-999)
    max_calls_sentinel_token = _effective_max_calls.set(-999)

    token, _random_part, _issued_at = _minted()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    try:
        result = await tool(ctx=mock_ctx, session_id=token)
        assert result == "ok"
        assert get_remaining_budget() == -999
        assert get_effective_max_calls() == -999
    finally:
        _remaining_budget.reset(remaining_sentinel_token)
        _effective_max_calls.reset(max_calls_sentinel_token)


@pytest.mark.asyncio
async def test_cancellation_restores_both_contextvars(enabled_session_gate, mock_ctx):
    token, _random_part, _issued_at = _minted()

    started = asyncio.Event()

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        started.set()
        await asyncio.sleep(10)

    task = asyncio.ensure_future(tool(ctx=mock_ctx, session_id=token))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert get_remaining_budget() is None
    assert get_effective_max_calls() is None
