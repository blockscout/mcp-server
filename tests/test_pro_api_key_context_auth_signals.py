# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the ctx-derived auth-origin and fingerprint helpers.

Kept in a focused sibling module rather than grown into
``tests/test_pro_api_key_context.py`` (already 466 LOC, close to the rule
``210`` 500-LOC limit) per the rule ``210`` guidance.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock

import pytest
from pro_api_key_helpers import ctx_with_header, ctx_with_malformed_header

from blockscout_mcp_server import pro_api_key_context
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import PRO_API_KEY_HASH_PREFIX
from blockscout_mcp_server.pro_api_key_context import (
    compute_auth_signals,
    extract_client_pro_api_key_from_ctx,
    resolve_pro_api_key,
)

_HEADER_NAME = "Blockscout-MCP-Pro-Api-Key"


def _expected_fingerprint(key: str) -> str:
    """Compute the expected fingerprint via the same UTF-8 byte construction."""
    return hashlib.sha256(f"{PRO_API_KEY_HASH_PREFIX}{key}".encode()).hexdigest()


# ===========================================================================
# Fingerprint safety: raw key never leaks; prefix actually participates
# ===========================================================================


def test_fingerprint_never_equals_or_contains_raw_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    raw_key = "super-secret-client-key-456"
    ctx = ctx_with_header(_HEADER_NAME, raw_key)
    fingerprint = compute_auth_signals(ctx)[1]
    assert fingerprint is not None
    assert fingerprint != raw_key
    assert raw_key not in fingerprint


def test_fingerprint_prefix_actually_participates(monkeypatch):
    """The result must differ from a hash computed without the domain-separation prefix."""
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    raw_key = "client-key-789"
    ctx = ctx_with_header(_HEADER_NAME, raw_key)
    fingerprint = compute_auth_signals(ctx)[1]
    unprefixed_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    assert fingerprint != unprefixed_hash


# ===========================================================================
# compute_auth_signals — the single source of truth for both signals
# ===========================================================================
#
# These cases pin the (origin, fingerprint) pairing per branch so the two signals
# can never silently diverge. A server key is configured throughout so a
# server-fallback regression cannot hide: a valid client header must still win and
# a malformed one must still yield no usable key (no silent fallback to the server
# key), mirroring the precedence enforced by resolve_pro_api_key().


def test_auth_signals_valid_client_returns_client_and_client_hash(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_signals(ctx) == ("client", _expected_fingerprint("client-key-123"))


def test_auth_signals_malformed_returns_none_and_no_fingerprint(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = ctx_with_malformed_header(_HEADER_NAME, "bad\nkey")
    assert compute_auth_signals(ctx) == ("none", None)


def test_auth_signals_absent_with_server_key_returns_server_and_server_hash(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_signals(ctx) == ("server", _expected_fingerprint("server-key"))


def test_auth_signals_absent_with_no_server_key_returns_none_and_no_fingerprint(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_signals(ctx) == ("none", None)


# ===========================================================================
# Server-key fingerprint memoization — the constant server hash is computed once
# ===========================================================================
#
# The server key is fixed for the process lifetime, so its SHA-256 is memoized
# (see _server_api_key_fingerprint) and the observability hot path reuses the one
# digest instead of re-hashing the same constant on every tool call / resource read.


def test_server_fingerprint_is_memoized_across_calls(monkeypatch):
    """Absent client key + server key -> ("server", <hash>), hashing the server key once.

    Pins the optimization that replaces the old ``include_server_fingerprint``
    gate: rather than skipping the hash when no consumer exists, the fixed server
    key is hashed once and reused. The spy below proves a second derivation reuses
    the memoized digest instead of re-running the SHA-256.
    """
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    pro_api_key_context._server_api_key_fingerprint.cache_clear()

    fingerprint_spy = MagicMock(side_effect=pro_api_key_context._fingerprint_pro_api_key)
    monkeypatch.setattr(pro_api_key_context, "_fingerprint_pro_api_key", fingerprint_spy)

    ctx = ctx_with_header(_HEADER_NAME, "")  # absent client key -> server fallback
    expected = ("server", _expected_fingerprint("server-key"))
    assert compute_auth_signals(ctx) == expected
    assert compute_auth_signals(ctx) == expected
    # Two derivations, but the constant server key was hashed exactly once.
    fingerprint_spy.assert_called_once_with("server-key")


def test_client_fingerprint_is_never_memoized(monkeypatch):
    """A per-request client key is re-hashed each call — only the server key is cached.

    The client-key path must never route through the memoizing helper: caching a
    per-request secret would both retain it and let a stale digest leak across
    requests. Two calls with a valid client header therefore hash it twice.
    """
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)

    fingerprint_spy = MagicMock(side_effect=pro_api_key_context._fingerprint_pro_api_key)
    monkeypatch.setattr(pro_api_key_context, "_fingerprint_pro_api_key", fingerprint_spy)

    ctx = ctx_with_header(_HEADER_NAME, "client-key-123")
    expected = ("client", _expected_fingerprint("client-key-123"))
    assert compute_auth_signals(ctx) == expected
    assert compute_auth_signals(ctx) == expected
    assert fingerprint_spy.call_count == 2


# ===========================================================================
# Coupling invariant: auth_origin must never disagree with resolve_pro_api_key
# ===========================================================================
#
# Both paths delegate precedence to _apply_key_precedence, so the reported origin
# and the key resolve_pro_api_key() actually uses are two views of one decision.
# This pins the end-to-end invariant directly (not just the shared helper): if a
# future edit re-introduces a divergent branch in either wrapper — the drift risk
# #423 exists to prevent — one of these cases fails. compute_auth_signals is
# driven from ctx headers; resolve_pro_api_key from the ContextVar set to the
# *same* state extracted from that ctx, so both see one logical input.


def _resolve_outcome(state: pro_api_key_context.ClientKeyState) -> tuple[str, str | None]:
    """Run ``resolve_pro_api_key`` with the ContextVar set to *state*; report its outcome.

    Returns ``("key", <value>)`` for a returned key (possibly ``""``) or
    ``("raised", None)`` when the malformed-key ``ValueError`` is raised.
    """
    token = pro_api_key_context._client_key_state.set(state)
    try:
        return "key", resolve_pro_api_key()
    except ValueError:
        return "raised", None
    finally:
        pro_api_key_context._client_key_state.reset(token)


@pytest.mark.parametrize(
    ("server_key", "make_ctx", "expected_origin", "expected_resolution"),
    [
        pytest.param(
            "server-key",
            lambda: ctx_with_header(_HEADER_NAME, "client-key-123"),
            "client",
            ("key", "client-key-123"),
            id="valid-client-wins",
        ),
        pytest.param(
            "server-key",
            lambda: ctx_with_malformed_header(_HEADER_NAME, "bad\nkey"),
            "none",
            ("raised", None),
            id="malformed-rejected-no-fallback",
        ),
        pytest.param(
            "server-key",
            lambda: ctx_with_header(_HEADER_NAME, ""),
            "server",
            ("key", "server-key"),
            id="absent-falls-back-to-server",
        ),
        pytest.param(
            "",
            lambda: ctx_with_header(_HEADER_NAME, ""),
            "none",
            ("key", ""),
            id="absent-no-server-key",
        ),
    ],
)
def test_auth_origin_stays_consistent_with_resolve_pro_api_key(
    monkeypatch, server_key, make_ctx, expected_origin, expected_resolution
):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", server_key, raising=False)
    pro_api_key_context._server_api_key_fingerprint.cache_clear()

    ctx = make_ctx()
    origin, _fingerprint = compute_auth_signals(ctx)
    assert origin == expected_origin

    # resolve sees the SAME state the telemetry path derived from ctx.
    state = extract_client_pro_api_key_from_ctx(ctx)
    resolution = _resolve_outcome(state)
    assert resolution == expected_resolution

    # The invariant tying the two together: a "usable key" origin iff resolve
    # yields a non-empty key; "none" iff resolve raises or yields "".
    if origin in ("client", "server"):
        assert resolution[0] == "key" and resolution[1]
    else:
        assert resolution == ("raised", None) or resolution == ("key", "")
