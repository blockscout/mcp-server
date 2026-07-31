# SPDX-License-Identifier: LicenseRef-Blockscout
"""Session-token mint/verify, typed gate errors, and gate/exemption predicates.

This module owns the request-independent policy for the session-gated free
tier (issue #442): it mints and verifies HMAC-signed ``session_id`` tokens,
defines the typed error hierarchy the decorators (Phase 4) raise, and exposes
the two predicates that decide whether gating applies at all
(:func:`gate_enabled`) and whether a given request is exempt from it
(:func:`client_supplied_valid_key`, re-exported from
:mod:`pro_api_key_context`).

Kept separate from ``tools/decorators.py`` for the same reason
``pro_api_key_context.py`` is: it owns a cross-cutting request-scoped policy,
not logging. It may import from ``config``, ``constants``, ``session_store``,
``pro_api_key_context``, and ``analytics`` — but must **not** import
``tools/common.py`` (Phase 5 makes ``tools/common.py`` import from *this*
module; keeping the dependency one-way avoids a cycle).

Token format
------------
A token is three ``.``-joined parts: ``random_part.issued_at.mac``.

- ``random_part`` comes from :func:`secrets.token_urlsafe` (>= 128 bits of
  entropy) and never contains the ``.`` separator (URL-safe base64 alphabet).
- ``issued_at`` is an integer unix timestamp (wall clock), rendered as decimal
  digits — also separator-free.
- ``mac`` is the hex HMAC-SHA256 of ``random_part + "." + issued_at`` *and the
  store generation* (see below), rendered as hex digits — also separator-free.

The MAC binds the store generation
-----------------------------------
The MAC covers ``HMAC-SHA256(secret, random_part + "." + issued_at + "." +
generation)`` — not just the random part and ``issued_at``. Signing only the
random part and appending ``issued_at`` unsigned would let a client forge its
own expiry. Binding in the generation (a random value minted once per SQLite
file, see ``session_store.py``) additionally means a replaced or lost session
database rejects every previously issued token as MAC-invalid, exactly like a
secret rotation — the recoverable path, where the agent re-initializes and
gets a fresh identifier. Without this, a database-only loss under a surviving
secret would silently restore every unexpired identifier's budget, including
exhausted ones, contradicting the requirement that state loss degrade to
invalidated sessions.

Verification performs no per-request store I/O: its only store-derived input
is the in-memory ``generation`` attribute the store loaded once at
``initialize()``.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import inspect
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    SESSION_ID_REQUIRED_MESSAGE,
    SESSION_OVER_MESSAGE,
    SESSION_STORE_UNAVAILABLE_MESSAGE,
)
from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.pro_api_key_context import client_supplied_valid_key
from blockscout_mcp_server.session_store import get_store

logger = logging.getLogger(__name__)

_SEPARATOR = "."
_MIN_MAC_HEX_LEN = 24  # ~96 bits; hmac.compare_digest still compares full hex strings.

__all__ = [
    "SessionGateError",
    "SessionIdMissingError",
    "SessionIdInvalidError",
    "SessionExpiredError",
    "SessionBudgetExhaustedError",
    "SessionStoreUnavailableError",
    "mint_token",
    "verify_token",
    "gate_enabled",
    "client_supplied_valid_key",
    "get_remaining_budget",
    "session_gate",
    "session_gate_unmetered",
]


# ---------------------------------------------------------------------------
# Typed error hierarchy
# ---------------------------------------------------------------------------
#
# Each subclasses `Exception` directly (never `ValueError`/`RuntimeError`):
# `handle_rest_errors` (Phase 8) has existing branches that map those built-ins
# to generic 400/500 responses, and those branches would swallow these errors
# before Phase 8's dedicated branches could run. In MCP mode these propagate
# and the framework converts them to `isError=True` responses (rule 110).


class SessionGateError(Exception):
    """Base class for all session-gate errors."""


class SessionIdMissingError(SessionGateError):
    """Raised when a gated tool call carries no `session_id` at all."""

    def __init__(self) -> None:
        super().__init__(SESSION_ID_REQUIRED_MESSAGE)


class SessionIdInvalidError(SessionGateError):
    """Raised when a `session_id` fails structural parsing or MAC verification."""

    def __init__(self) -> None:
        super().__init__(SESSION_ID_REQUIRED_MESSAGE)


class SessionExpiredError(SessionGateError):
    """Raised when a `session_id` is well-formed and MAC-valid, but past its TTL."""

    def __init__(self) -> None:
        super().__init__(SESSION_OVER_MESSAGE)


class SessionBudgetExhaustedError(SessionGateError):
    """Raised when a `session_id`'s call budget has been used up."""

    def __init__(self) -> None:
        super().__init__(SESSION_OVER_MESSAGE)


class SessionStoreUnavailableError(SessionGateError):
    """Raised when the session store cannot service a request (runtime fault)."""

    def __init__(self) -> None:
        super().__init__(SESSION_STORE_UNAVAILABLE_MESSAGE)


# ---------------------------------------------------------------------------
# Generation accessor
# ---------------------------------------------------------------------------


def _current_generation() -> str:
    """Return the initialized session store's generation.

    A single internal accessor so tests can monkeypatch it instead of standing
    up a real store, and so the mint/verify functions below share one call
    site. Whenever mint/verify can run, the store is initialized by
    construction: the gate requires `gate_enabled()`, and Phase 9 initializes
    the store before serving whenever the secret is set in HTTP mode.
    """
    return get_store().generation


# ---------------------------------------------------------------------------
# MAC computation
# ---------------------------------------------------------------------------


def _compute_mac(random_part: str, issued_at: int, generation: str) -> str:
    payload = f"{random_part}{_SEPARATOR}{issued_at}{_SEPARATOR}{generation}".encode()
    return hmac.new(config.session_secret.encode(), payload, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Mint / verify
# ---------------------------------------------------------------------------


def mint_token() -> str:
    """Mint a fresh `session_id` token.

    Requires a non-empty `config.session_secret`. Writes nothing to the
    store — unlock stays a pure function; identifiers that are never used
    leave no rows behind.

    Raises:
        SessionGateError: if `config.session_secret` is empty.
    """
    if not config.session_secret:
        raise SessionGateError("Cannot mint a session token: BLOCKSCOUT_SESSION_SECRET is not configured.")

    random_part = secrets.token_urlsafe(16)  # 128 bits of entropy.
    issued_at = int(time.time())
    generation = _current_generation()
    mac = _compute_mac(random_part, issued_at, generation)
    return f"{random_part}{_SEPARATOR}{issued_at}{_SEPARATOR}{mac}"


def verify_token(token: str) -> tuple[str, int]:
    """Verify `token` and return its `(random_part, issued_at)` on success.

    Performs no per-request store I/O: the only store-derived input is the
    in-memory `generation` attribute the store loaded once at
    `initialize()`.

    Raises:
        SessionIdInvalidError: the token is structurally malformed, or its MAC
            does not verify against the current secret and store generation.
        SessionExpiredError: the token is well-formed and MAC-valid, but its
            `issued_at + config.session_ttl_seconds` is in the past, or its
            `issued_at` is in the future (an NTP step backwards must not
            extend a token's life beyond the TTL, so a future `issued_at` is
            treated as expired rather than invalid).
    """
    parts = token.split(_SEPARATOR)
    if len(parts) != 3:
        raise SessionIdInvalidError()

    random_part, issued_at_str, mac = parts
    if not random_part or not issued_at_str or not mac:
        raise SessionIdInvalidError()

    # `str.isdigit` alone also accepts non-ASCII digit forms: some crash int()
    # with a bare ValueError that would bypass the typed error hierarchy (e.g.
    # superscripts), others parse as alternate encodings of a valid token
    # (e.g. Arabic-Indic digits). Only the canonical ASCII rendering — the one
    # the MAC is computed over — may verify.
    if not (issued_at_str.isascii() and issued_at_str.isdigit()):
        raise SessionIdInvalidError()
    issued_at = int(issued_at_str)

    if len(mac) < _MIN_MAC_HEX_LEN:
        raise SessionIdInvalidError()

    generation = _current_generation()
    expected_mac = _compute_mac(random_part, issued_at, generation)
    if not hmac.compare_digest(mac, expected_mac):
        raise SessionIdInvalidError()

    now = time.time()
    if issued_at > now:
        # A clock step backwards must not extend the token's life.
        raise SessionExpiredError()
    if issued_at + config.session_ttl_seconds < now:
        raise SessionExpiredError()

    return random_part, issued_at


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def gate_enabled() -> bool:
    """Return whether the session gate is active for the current process.

    Mirrors the existing two-condition idiom at `telemetry.py`
    (`analytics.is_http_mode_enabled() and config.mixpanel_token`). The
    HTTP-mode condition is causal, not decorative: the exemption path needs a
    request header, and stdio has none — enabling the gate in stdio would
    make exemption impossible for everyone.
    """
    return bool(config.session_secret) and analytics.is_http_mode_enabled()


# ---------------------------------------------------------------------------
# Request-scoped remaining-budget value
# ---------------------------------------------------------------------------
#
# Set/reset around the wrapped call exactly the way `pro_api_key_context.py`
# manages its ContextVars: `set()` returns a token, `reset()` runs in
# `finally`, so the value never leaks across requests. `None` means "no
# gate-derived budget for this call" — the gate is disabled, the caller is
# exempt, or no decorator has run yet. Phase 5's response-note renderer is
# this accessor's only consumer.

_remaining_budget: ContextVar[int | None] = ContextVar("_remaining_budget", default=None)


def get_remaining_budget() -> int | None:
    """Return the current request's remaining session budget, or `None` if none applies."""
    return _remaining_budget.get()


# ---------------------------------------------------------------------------
# Store chokepoint — degraded mode, never shutdown
# ---------------------------------------------------------------------------
#
# Every store access in both decorators below funnels through these three
# helpers. A store fault logs the true cause at ERROR level (the operator's
# only truthful signal) and raises `SessionStoreUnavailableError` (the
# agent-facing nudge) — the tool body is never invoked on a store fault, so no
# fault direction yields unmetered access. `_refund` is the one exception:
# it must never raise, because a failed refund must not mask the tool's own
# error (see `session_gate`'s docstring).


def _log_store_fault(operation: str, exc: Exception) -> None:
    logger.error("session store failure (%s): %s", operation, exc)


def _increment(random_part: str, issued_at: int) -> int | None:
    try:
        return get_store().check_and_increment(random_part, issued_at)
    except Exception as exc:
        _log_store_fault("check_and_increment", exc)
        raise SessionStoreUnavailableError() from exc


def _read_calls(random_part: str) -> int:
    try:
        return get_store().get_calls(random_part)
    except Exception as exc:
        _log_store_fault("get_calls", exc)
        raise SessionStoreUnavailableError() from exc


def _refund(random_part: str) -> None:
    """Best-effort refund. Never raises — a failed refund must not mask the tool's own error."""
    try:
        get_store().refund(random_part)
    except Exception as exc:
        _log_store_fault("refund", exc)


# ---------------------------------------------------------------------------
# Pagination continuation injection
# ---------------------------------------------------------------------------


def _inject_session_id_into_pagination(result: Any, session_id: str) -> Any:
    """Stamp the presented `session_id` onto a successful response's pagination continuation.

    The documented pagination contract is to replay the complete `next_call.params`
    object verbatim, so a gated continuation without the identifier would die with
    `SessionIdMissingError` on every paginated tool. A no-op when `result` carries no
    `pagination` (or is not a `ToolResponse` at all).
    """
    if isinstance(result, ToolResponse) and result.pagination is not None:
        result.pagination.next_call.params["session_id"] = session_id
    return result


# ---------------------------------------------------------------------------
# Bound-argument extraction
# ---------------------------------------------------------------------------


def _extract_session_id(sig: inspect.Signature, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    """Read `session_id` from the call's bound arguments (mirrors `log_tool_invocation`)."""
    bound = sig.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments).get("session_id", None)


# ---------------------------------------------------------------------------
# The metered decorator
# ---------------------------------------------------------------------------


def session_gate(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator enforcing the metered session gate on a tool function.

    Per call:

    1. Gate disabled (`gate_enabled()` is `False`) → call straight through.
    2. Exempt caller (`client_supplied_valid_key()`) → call straight through, no
       store access, no note.
    3. Missing/empty `session_id` → `SessionIdMissingError`.
    4. `verify_token` → `SessionIdInvalidError` or `SessionExpiredError`, both
       raised before any store I/O.
    5. `check_and_increment` — a store fault becomes `SessionStoreUnavailableError`;
       an exhausted budget (`None` result) becomes `SessionBudgetExhaustedError`.
    6. The remaining-budget ContextVar is set to `config.session_max_calls - calls`.
    7. The tool body runs. On any failure — including cancellation — the debit is
       refunded before the original exception (or `BaseException`, e.g.
       `asyncio.CancelledError`) is re-raised unchanged. A refusal in steps 3-5
       consumed nothing, so nothing is refunded for those.
    8. On success, if the response carries `pagination`, the presented `session_id`
       is stamped onto `next_call.params`.

    Stacking: must be applied *below* `@pro_api_key_scope` (exemption reads a
    ContextVar only that scope populates) and *above* `@pro_api_credit_scope`
    (which must stay innermost, closest to the tool body).
    """
    sig = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not gate_enabled():
            return await func(*args, **kwargs)
        if client_supplied_valid_key():
            return await func(*args, **kwargs)

        session_id = _extract_session_id(sig, args, kwargs)
        if not session_id:
            raise SessionIdMissingError()

        random_part, issued_at = verify_token(session_id)

        calls = _increment(random_part, issued_at)
        if calls is None:
            raise SessionBudgetExhaustedError()

        budget_token = _remaining_budget.set(config.session_max_calls - calls)
        try:
            try:
                result = await func(*args, **kwargs)
            except BaseException:
                _refund(random_part)
                raise
        finally:
            _remaining_budget.reset(budget_token)

        return _inject_session_id_into_pagination(result, session_id)

    return wrapper


# ---------------------------------------------------------------------------
# The gated-but-not-metered variant (get_chains_list only)
# ---------------------------------------------------------------------------


def session_gate_unmetered(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator enforcing the gate without metering (`get_chains_list` only).

    Shares steps 1-4 of `session_gate` (disabled / exempt / missing / invalid /
    expired), but instead of incrementing performs a read-only `get_calls` lookup
    and sets the remaining-budget ContextVar to `max(0, config.session_max_calls -
    calls)` — a fresh identifier (no row) reports the full configured budget, and
    the floor guarantees a successful response never reports a negative remaining
    budget even if `session_max_calls` was lowered below an identifier's already-
    recorded count. Does not check exhaustion: a spent-but-unexpired identifier
    still navigates (it just reports 0 remaining); only expiry blocks it.

    Performs the same pagination-injection step as `session_gate`.
    """
    sig = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not gate_enabled():
            return await func(*args, **kwargs)
        if client_supplied_valid_key():
            return await func(*args, **kwargs)

        session_id = _extract_session_id(sig, args, kwargs)
        if not session_id:
            raise SessionIdMissingError()

        random_part, _issued_at = verify_token(session_id)

        calls = _read_calls(random_part)
        remaining = max(0, config.session_max_calls - calls)

        budget_token = _remaining_budget.set(remaining)
        try:
            result = await func(*args, **kwargs)
        finally:
            _remaining_budget.reset(budget_token)

        return _inject_session_id_into_pagination(result, session_id)

    return wrapper
