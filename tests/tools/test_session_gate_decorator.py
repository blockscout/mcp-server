# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the @session_gate decorator's core branches.

Uses small dummy async functions (never real tool modules) to prove: disabled
gate, exemption, missing/invalid/expired tokens, the metered happy path and
exhaustion, refund-on-failure and refund-on-cancellation semantics, store-fault
handling, and database-replacement invalidation (Issue #442, Phase 4).

Pagination injection, the `@session_gate_unmetered` variant, decorator
stacking order, malformed-key precedence, and the sweep-vs-token invariant
live in `tests/tools/test_session_gate_decorator_composition.py` (split to
keep both files under the ~500 LOC guideline).
"""

from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import MagicMock

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    SESSION_ID_REQUIRED_MESSAGE,
    SESSION_OVER_MESSAGE,
    SESSION_STORE_UNAVAILABLE_MESSAGE,
)
from blockscout_mcp_server.session_gate import (
    SessionBudgetExhaustedError,
    SessionExpiredError,
    SessionIdInvalidError,
    SessionIdMissingError,
    SessionStoreUnavailableError,
    get_remaining_budget,
    mint_token,
    session_gate,
    verify_token,
)
from blockscout_mcp_server.session_store import close_store, get_store, initialize_store


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
# Disabled / exempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_gate_calls_through_untouched(mock_ctx):
    calls = {"n": 0}

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        calls["n"] += 1
        return "ok"

    result = await tool(ctx=mock_ctx)

    assert result == "ok"
    assert calls["n"] == 1
    assert get_remaining_budget() is None


@pytest.mark.asyncio
async def test_exempt_caller_calls_through_with_no_session_id(enabled_session_gate, store_spy, monkeypatch, mock_ctx):
    monkeypatch.setattr("blockscout_mcp_server.session_gate.client_supplied_valid_key", lambda: True)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        return "ok"

    result = await tool(ctx=mock_ctx)

    assert result == "ok"
    assert get_remaining_budget() is None
    store_spy.check_and_increment.assert_not_called()
    store_spy.get_calls.assert_not_called()


# ---------------------------------------------------------------------------
# Missing / invalid / expired session_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_session_id_raises_and_never_calls_body(enabled_session_gate, store_spy, mock_ctx):
    calls = {"n": 0}

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        calls["n"] += 1
        return "ok"

    with pytest.raises(SessionIdMissingError) as exc_info:
        await tool(ctx=mock_ctx)

    assert str(exc_info.value) == SESSION_ID_REQUIRED_MESSAGE
    assert calls["n"] == 0
    store_spy.check_and_increment.assert_not_called()
    store_spy.refund.assert_not_called()


@pytest.mark.asyncio
async def test_garbage_token_raises_invalid_with_no_store_io(enabled_session_gate, store_spy, mock_ctx):
    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionIdInvalidError):
        await tool(ctx=mock_ctx, session_id="not-a-real-token")

    store_spy.check_and_increment.assert_not_called()
    store_spy.get_calls.assert_not_called()
    store_spy.refund.assert_not_called()


@pytest.mark.asyncio
async def test_expired_token_raises_expired_with_no_store_io(enabled_session_gate, store_spy, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()

    monkeypatch.setattr(time, "time", lambda: now + 101)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionExpiredError):
        await tool(ctx=mock_ctx, session_id=token)

    store_spy.check_and_increment.assert_not_called()
    store_spy.get_calls.assert_not_called()
    store_spy.refund.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path / exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_increments_and_sets_budget(enabled_session_gate, store_spy, mock_ctx):
    token, random_part, issued_at = _minted()

    observed_budget = {}

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        observed_budget["value"] = get_remaining_budget()
        return "ok"

    result = await tool(ctx=mock_ctx, session_id=token)

    assert result == "ok"
    store_spy.check_and_increment.assert_called_once_with(random_part, issued_at)
    assert observed_budget["value"] == config.session_max_calls - 1
    assert get_remaining_budget() is None  # reset after the call


@pytest.mark.asyncio
async def test_exhaustion_raises_and_refund_not_attempted(enabled_session_gate, store_spy, monkeypatch, mock_ctx):
    monkeypatch.setattr(config, "session_max_calls", 1)
    token, random_part, issued_at = _minted()

    calls = {"n": 0}

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        calls["n"] += 1
        return "ok"

    # First call consumes the single unit of budget.
    await tool(ctx=mock_ctx, session_id=token)
    assert calls["n"] == 1
    store_spy.refund.reset_mock()

    # Second call is exhausted.
    with pytest.raises(SessionBudgetExhaustedError) as exc_info:
        await tool(ctx=mock_ctx, session_id=token)

    assert str(exc_info.value) == SESSION_OVER_MESSAGE
    assert calls["n"] == 1  # body not invoked a second time
    store_spy.refund.assert_not_called()


# ---------------------------------------------------------------------------
# Refund on failure / cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_call_refunds_and_reraises(enabled_session_gate, mock_ctx):
    token, random_part, _issued_at = _minted()
    store = get_store()
    before = store.get_calls(random_part)

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await tool(ctx=mock_ctx, session_id=token)

    assert store.get_calls(random_part) == before
    assert get_remaining_budget() is None


@pytest.mark.asyncio
async def test_cancellation_refunds_and_propagates(enabled_session_gate, mock_ctx):
    token, random_part, _issued_at = _minted()
    store = get_store()
    before = store.get_calls(random_part)

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

    assert store.get_calls(random_part) == before


@pytest.mark.asyncio
async def test_cancellation_with_refund_failure_still_propagates_cancelled(
    enabled_session_gate, monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx
):
    caplog.set_level(logging.ERROR, logger="blockscout_mcp_server.session_gate")
    token, _random_part, _issued_at = _minted()

    store = get_store()
    monkeypatch.setattr(store, "refund", MagicMock(side_effect=RuntimeError("store fault")))

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

    assert "session store failure (refund)" in caplog.text


@pytest.mark.asyncio
async def test_refund_failure_does_not_mask_original_exception(
    enabled_session_gate, monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx
):
    caplog.set_level(logging.ERROR, logger="blockscout_mcp_server.session_gate")
    token, _random_part, _issued_at = _minted()

    store = get_store()
    monkeypatch.setattr(store, "refund", MagicMock(side_effect=RuntimeError("store fault")))

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise ValueError("original failure")

    with pytest.raises(ValueError, match="original failure"):
        await tool(ctx=mock_ctx, session_id=token)

    assert "session store failure (refund)" in caplog.text


# ---------------------------------------------------------------------------
# Store fault on increment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_fault_on_increment_raises_unavailable(enabled_session_gate, monkeypatch, mock_ctx):
    token, _random_part, _issued_at = _minted()
    calls = {"n": 0}

    store = get_store()
    monkeypatch.setattr(store, "check_and_increment", MagicMock(side_effect=RuntimeError("disk full")))

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        calls["n"] += 1
        return "ok"

    with pytest.raises(SessionStoreUnavailableError) as exc_info:
        await tool(ctx=mock_ctx, session_id=token)

    assert str(exc_info.value) == SESSION_STORE_UNAVAILABLE_MESSAGE
    assert calls["n"] == 0


# ---------------------------------------------------------------------------
# Database replacement invalidates, never re-budgets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prior_calls", [0, 1, 5])
@pytest.mark.asyncio
async def test_database_replacement_invalidates_old_token(enabled_session_gate, tmp_path, mock_ctx, prior_calls):
    token, random_part, issued_at = _minted()
    store = get_store()
    for _ in range(prior_calls):
        store.check_and_increment(random_part, issued_at)

    # Replace the database file entirely: a fresh generation is minted.
    close_store()
    new_db_path = tmp_path / "replacement.db"
    initialize_store(str(new_db_path))

    @session_gate
    async def tool(ctx, session_id: str | None = None):
        raise AssertionError("must not be called")

    with pytest.raises(SessionIdInvalidError):
        await tool(ctx=mock_ctx, session_id=token)

    # No fresh row was created for the old identifier under the new generation.
    assert get_store().get_calls(random_part) == 0
