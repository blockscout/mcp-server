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

import hashlib
import hmac
import secrets
import time

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    SESSION_ID_REQUIRED_MESSAGE,
    SESSION_OVER_MESSAGE,
    SESSION_STORE_UNAVAILABLE_MESSAGE,
)
from blockscout_mcp_server.pro_api_key_context import client_supplied_valid_key
from blockscout_mcp_server.session_store import get_store

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

    if not issued_at_str.isdigit():
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
