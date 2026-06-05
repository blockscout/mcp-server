# SPDX-License-Identifier: LicenseRef-Blockscout
"""Request-scoped PRO API key resolution for MCP tool calls.

This module owns everything about a client-supplied PRO API key:
- An immutable state representation (absent / valid / malformed).
- A module-level ContextVar holding that state.
- A normalization/validation helper.
- An extractor that reads the key from an MCP context.
- A resolver that applies the client-key → server-key precedence rule.
- A @pro_api_key_scope decorator that populates the ContextVar per request.

Kept intentionally separate from tools/decorators.py so authentication and
observability remain decoupled.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from blockscout_mcp_server.client_meta import get_header_case_insensitive
from blockscout_mcp_server.config import config

# ---------------------------------------------------------------------------
# Maximum length accepted for a client-supplied PRO API key value.
# Large enough for any real key or JWT; small enough to reject abuse.
# ---------------------------------------------------------------------------
_MAX_KEY_LENGTH = 4096


# ---------------------------------------------------------------------------
# 1. Immutable state representation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Absent:
    """No client key was provided (feature disabled / not an MCP call / blank header)."""


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
# 2. Module-level ContextVar (not per-call — required for correct semantics)
# ---------------------------------------------------------------------------

_client_key_state: ContextVar[ClientKeyState] = ContextVar("_client_key_state", default=_ABSENT)


# ---------------------------------------------------------------------------
# 3. Normalization / validation helper
# ---------------------------------------------------------------------------


def _normalize_key(raw: Any) -> ClientKeyState:
    """Return one of the three states for *raw* header value.

    - Non-string → absent (guards against MagicMock in tests).
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
# 4. Extractor — reads the header from an MCP context
# ---------------------------------------------------------------------------


def extract_client_pro_api_key_from_ctx(ctx: Any) -> ClientKeyState:
    """Extract the client PRO API key state from an MCP context.

    Returns *absent* when:
    - The feature is disabled (``config.pro_api_key_header`` is empty).
    - The call comes from the REST layer (``ctx.call_source == "rest"``).
    - There is no HTTP request context (e.g. stdio transport).
    - Any unexpected context shape is encountered.

    Never raises.
    """
    try:
        if not config.pro_api_key_header:
            return _ABSENT

        if getattr(ctx, "call_source", None) == "rest":
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
# 6. Decorator — populates the ContextVar for the duration of a tool call
# ---------------------------------------------------------------------------


def pro_api_key_scope(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator that records the per-request client PRO API key state.

    Wraps an async tool function.  Extracts ``ctx`` from the call arguments
    (positional or keyword), resolves the client key state, sets the ContextVar,
    and resets it in ``finally`` regardless of outcome.

    The decorator **never raises** for a malformed key — it only records state.
    The raise happens later in ``resolve_pro_api_key()`` at the PRO API chokepoint.

    Uses ``functools.wraps`` to preserve the wrapped function's signature so
    FastMCP schema generation and REST parameter binding continue to work.
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
