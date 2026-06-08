# SPDX-License-Identifier: LicenseRef-Blockscout
"""Request-scoped PRO API key resolution and credit-tracking for HTTP tool calls.

This module owns everything about a client-supplied PRO API key and the
per-request remaining-credits observation:

- An immutable state representation (absent / valid / malformed).
- A module-level ContextVar holding that state.
- A normalization/validation helper.
- An extractor that reads the key from any HTTP request context (MCP-over-HTTP
  or REST).
- A resolver that applies the client-key → server-key precedence rule.
- A ``require_pro_api_key()`` helper that wraps the resolver with the standard
  not-configured error so every PRO API entry point raises the same message.
- A @pro_api_key_scope decorator that populates the ContextVar per request.
- A ``CreditSink`` mutable box and ``_credit_sink`` ContextVar for tracking the
  minimum ``x-credits-remaining`` value observed across all PRO API calls within
  a single tool invocation.

Kept intentionally separate from tools/decorators.py so authentication and
observability remain decoupled.

Blanket decorator application
-----------------------------
``@pro_api_key_scope`` is applied to *every* MCP tool, including tools that
never call the PRO API (e.g. ``get_chains_list``, ``get_address_by_ens_name``,
``__unlock_blockchain_analysis__``).  For those tools the recorded state is
never consulted — a malformed client header is effectively a no-op — but
applying the decorator uniformly means a future contributor cannot accidentally
add a PRO API call to a tool that lacks request-scoped key resolution.  Do not
"optimize" by removing it from a tool that today doesn't need it.

Credit-sink box design
----------------------
``_credit_sink`` stores a *mutable* ``CreditSink`` object rather than a plain
``ContextVar[float | None]``.  In asyncio, a child task spawned by
``asyncio.gather`` or an ``anyio`` task group runs in a **copied** context, so
a child calling ``ContextVar.set(...)`` would not be visible to the parent.
Storing a mutable box in the ContextVar sidesteps this: the copied context
shares the *same object reference*, so a child that **mutates** the box is
immediately visible to the parent.

The minimum value is retained (rather than the latest) because it is the
conservative choice — it warns earlier — and it is order-independent across
concurrent requests where completion order is non-deterministic.
"""

from __future__ import annotations

import functools
import inspect
import logging
import math
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from blockscout_mcp_server.client_meta import get_header_case_insensitive
from blockscout_mcp_server.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Maximum length accepted for a client-supplied PRO API key value.
# Blockscout PRO API keys are 79 characters today; 256 leaves ~4x headroom for
# future format changes while still rejecting obvious abuse (multi-KB payloads
# that would only inflate the per-invocation ContextVar / log paths).
# ---------------------------------------------------------------------------
_MAX_KEY_LENGTH = 256


# ---------------------------------------------------------------------------
# 1. Immutable state representation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Absent:
    """No client key was provided (feature disabled / non-HTTP transport / blank header)."""


@dataclass(frozen=True)
class _Valid:
    """A well-formed client key string (local validation only)."""

    value: str


@dataclass(frozen=True)
class _Malformed:
    """A key was supplied but failed local validation."""


# Public type alias for the three states.
ClientKeyState = _Absent | _Valid | _Malformed

_ABSENT: ClientKeyState = _Absent()
_MALFORMED: ClientKeyState = _Malformed()


# ---------------------------------------------------------------------------
# 2. Module-level ContextVars (not per-call — required for correct semantics)
# ---------------------------------------------------------------------------

_client_key_state: ContextVar[ClientKeyState] = ContextVar("_client_key_state", default=_ABSENT)


# ---------------------------------------------------------------------------
# 2b. CreditSink — mutable box for the per-invocation remaining-credits value
# ---------------------------------------------------------------------------


class CreditSink:
    """Mutable box that records the minimum ``x-credits-remaining`` value seen.

    Stored in ``_credit_sink`` (a module-level ContextVar).  Because asyncio
    child tasks receive a *copy* of the parent context, a plain
    ``ContextVar[float]`` set inside a child would be invisible to the parent.
    Storing a mutable object instead means both parent and child share the same
    reference, so a child that *mutates* the box is immediately visible to the
    parent.

    The minimum is retained (rather than the latest) as the conservative choice:
    it warns earlier and is order-independent across concurrent requests.

    Invariant: ``remaining`` is either ``None`` or a *finite* float.  See
    :meth:`record` for why non-finite values are rejected at the door.
    """

    def __init__(self) -> None:
        self.remaining: float | None = None

    def record(self, value: float) -> None:
        """Update the stored minimum with *value*.

        First observation sets the value; subsequent observations only lower it.

        Non-finite values (``nan``, ``+inf``, ``-inf``) are silently ignored so
        the invariant "``remaining`` is ``None`` or a *finite* float" always
        holds.  This is the single chokepoint every value enters through, so the
        guard belongs here:
        - ``float("-Infinity")`` would otherwise crash a downstream
          ``int(remaining)`` display conversion with ``OverflowError``.
        - A ``nan`` (or ``-inf``) recorded first would *poison* the minimum: the
          ``value < self.remaining`` comparison is ``False`` for every later
          real observation (``x < nan`` is always ``False``; nothing is ``<
          -inf``), so a genuine low balance would be dropped and the advisory
          note silently suppressed for the whole invocation.
        """
        if not math.isfinite(value):
            return
        if self.remaining is None or value < self.remaining:
            self.remaining = value


# ``None`` default: code paths that build a response without a decorator-
# established sink (e.g. isolated unit tests) must see "no sink" and stay
# silent, not share a leaked box.
_credit_sink: ContextVar[CreditSink | None] = ContextVar("_credit_sink", default=None)


# ---------------------------------------------------------------------------
# 3. Normalization / validation helper
# ---------------------------------------------------------------------------


def _normalize_key(raw: Any) -> ClientKeyState:
    """Return one of the three states for *raw* header value.

    - Non-string → absent (defensive against unexpected mapping shapes).
    - Empty / blank after stripping → absent.
    - Contains control characters or exceeds max length → malformed.
    - Otherwise → valid with the stripped value.
    """
    if not isinstance(raw, str):
        return _ABSENT

    stripped = raw.strip()
    if not stripped:
        return _ABSENT

    if len(stripped) > _MAX_KEY_LENGTH:
        return _MALFORMED

    if any(ord(c) < 32 or ord(c) == 127 for c in stripped):
        return _MALFORMED

    return _Valid(value=stripped)


# ---------------------------------------------------------------------------
# 4. Extractor — reads the header from any HTTP request context
# ---------------------------------------------------------------------------


def extract_client_pro_api_key_from_ctx(ctx: Any) -> ClientKeyState:
    """Extract the client PRO API key state from an HTTP request context.

    Returns *absent* when:
    - The feature is disabled (``config.pro_api_key_header`` is empty).
    - There is no HTTP request context (e.g. stdio transport).
    - Any unexpected context shape is encountered.

    Never raises.
    """
    try:
        if not config.pro_api_key_header:
            return _ABSENT

        request_context = getattr(ctx, "request_context", None)
        if request_context is None:
            return _ABSENT

        request = getattr(request_context, "request", None)
        if request is None:
            return _ABSENT

        headers = getattr(request, "headers", None)
        if headers is None:
            return _ABSENT

        raw = get_header_case_insensitive(headers, config.pro_api_key_header, "")
        return _normalize_key(raw)

    except Exception:
        # Defensive: an unexpected ctx shape (e.g. after an MCP transport
        # upgrade) must never break the auth path.  Log at DEBUG so the bug is
        # discoverable without breaking the request.
        logger.debug("Unexpected error extracting client PRO API key from ctx", exc_info=True)
        return _ABSENT


# ---------------------------------------------------------------------------
# 5. Resolver — applies client-key → server-key precedence
# ---------------------------------------------------------------------------


def resolve_pro_api_key() -> str:
    """Return the effective PRO API key for the current request.

    Precedence:
    1. Client-supplied key (valid) → use it.
    2. Client-supplied key (malformed) → raise ``ValueError`` immediately.
       No fallback to the server key for a malformed submission.
    3. No client key (absent) → return ``config.pro_api_key`` (may be ``""``).

    Callers' existing emptiness guards handle the ``""`` case.
    """
    state = _client_key_state.get()

    if isinstance(state, _Valid):
        return state.value

    if isinstance(state, _Malformed):
        raise ValueError(
            "The supplied PRO API key header value is malformed: it contains control characters "
            "or exceeds the maximum allowed length. Please provide a valid key."
        )

    # _Absent — fall back to the configured server key.
    return config.pro_api_key


# ---------------------------------------------------------------------------
# 6. require_pro_api_key — single chokepoint for the "not configured" error
# ---------------------------------------------------------------------------


def require_pro_api_key(disabled_feature: str) -> str:
    """Return the effective PRO API key or raise the standard not-configured error.

    Propagates ``ValueError`` from :func:`resolve_pro_api_key` for a malformed
    client key.  When both the client key and the server key are absent, raises
    a ``ValueError`` whose message names ``BLOCKSCOUT_PRO_API_KEY`` and — when
    client-supplied keys are enabled — the configured request header.  Callers
    pass a short ``disabled_feature`` label ("data access", "address metadata",
    "contract reads via the PRO API gateway") so the caller's context survives
    without each call site duplicating the full sentence.
    """
    key = resolve_pro_api_key()
    if not key:
        hint = "set BLOCKSCOUT_PRO_API_KEY"
        if config.pro_api_key_header:
            hint = f"set BLOCKSCOUT_PRO_API_KEY on the server, or send the {config.pro_api_key_header} request header"
        raise ValueError(f"Blockscout PRO API key is not configured ({hint}); {disabled_feature} is disabled.")
    return key


# ---------------------------------------------------------------------------
# 7. Decorator — populates the ContextVar for the duration of a tool call
# ---------------------------------------------------------------------------


def pro_api_credit_scope(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator that establishes a fresh ``CreditSink`` per tool invocation.

    Creates and installs a new :class:`CreditSink` in ``_credit_sink`` *before*
    the tool body (and before any child task is spawned via ``asyncio.gather``
    or ``make_request_with_periodic_progress``), so all concurrent child tasks
    inherit the same mutable box and their credit observations are visible to the
    parent.  Resets the ContextVar to its prior value in ``finally`` so credit
    state never leaks between sequential invocations.

    Transport-agnostic: the sink is established unconditionally in every
    transport (MCP, REST, test stubs) because credit capture and the advisory
    low-credits note are required in both MCP and REST modes.  The decorator
    reads nothing from ``ctx`` — it only manages the box's lifetime.

    Separate from both ``@pro_api_key_scope`` (authentication concern) and
    ``log_tool_invocation`` (observability concern): folding credit lifecycle
    into either would mislead future readers.  ``pro_api_key_context.py``
    already owns all request-scoped PRO API state, making it the natural home
    for this sibling decorator.

    Stacking order
    --------------
    Apply this decorator *innermost* (closest to the function definition)::

        @log_tool_invocation
        @pro_api_key_scope
        @pro_api_credit_scope
        async def my_tool(...): ...

    This keeps the sink's lifetime tightest around the tool body.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = _credit_sink.set(CreditSink())
        try:
            return await func(*args, **kwargs)
        finally:
            _credit_sink.reset(token)

    return wrapper


def pro_api_key_scope(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator that records the per-request client PRO API key state.

    Wraps an async tool function.  Extracts ``ctx`` from the call arguments
    (positional or keyword), resolves the client key state, sets the ContextVar,
    and resets it in ``finally`` regardless of outcome.

    The decorator **never raises** for a malformed key — it only records state.
    The raise happens later in ``resolve_pro_api_key()`` at the PRO API chokepoint.

    Uses ``functools.wraps`` to preserve the wrapped function's signature so
    FastMCP schema generation and REST parameter binding continue to work.

    Stacking order
    --------------
    Apply this decorator *inside* (closer to the function than)
    ``@log_tool_invocation`` — that is::

        @log_tool_invocation
        @pro_api_key_scope
        async def my_tool(...): ...

    Consequence: ``log_tool_invocation`` (and the analytics call it makes) runs
    *outside* this scope and therefore cannot read the ContextVar.  Analytics
    must continue to derive any client-supplied-key signal from ``ctx`` headers
    directly, never from ``_client_key_state``.
    """
    sig = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        ctx = dict(bound.arguments).get("ctx", None)

        state = extract_client_pro_api_key_from_ctx(ctx)
        token = _client_key_state.set(state)
        try:
            return await func(*args, **kwargs)
        finally:
            _client_key_state.reset(token)

    return wrapper
