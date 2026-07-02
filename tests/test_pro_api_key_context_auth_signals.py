# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the ctx-derived auth-origin and fingerprint helpers.

Kept in a focused sibling module rather than grown into
``tests/test_pro_api_key_context.py`` (already 466 LOC, close to the rule
``210`` 500-LOC limit) per the rule ``210`` guidance.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from starlette.datastructures import Headers

from blockscout_mcp_server import pro_api_key_context
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import PRO_API_KEY_HASH_PREFIX
from blockscout_mcp_server.pro_api_key_context import compute_auth_signals

_HEADER_NAME = "Blockscout-MCP-Pro-Api-Key"


def _ctx_with_header(header_name: str, header_value: str) -> SimpleNamespace:
    """Build a minimal MCP-like context carrying *header_value* under *header_name*.

    Mirrors the helper in ``tests/test_pro_api_key_context.py``.
    """
    headers = Headers(headers={header_name.upper(): header_value})
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def _ctx_with_malformed_header(header_name: str, header_value: str) -> SimpleNamespace:
    """Build a context whose header value contains control characters.

    Uses a plain dict so a value that real ``starlette.datastructures.Headers``
    would refuse to encode can still be injected (mirrors the equivalent helper
    usage in ``tests/test_pro_api_key_context.py``).
    """
    headers = {header_name: header_value}
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def _expected_fingerprint(key: str) -> str:
    """Compute the expected fingerprint via the same explicit UTF-8 byte construction."""
    return hashlib.sha256(f"{PRO_API_KEY_HASH_PREFIX}{key}".encode("utf-8")).hexdigest()  # noqa: UP012


# ===========================================================================
# Fingerprint safety: raw key never leaks; prefix actually participates
# ===========================================================================


def test_fingerprint_never_equals_or_contains_raw_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    raw_key = "super-secret-client-key-456"
    ctx = _ctx_with_header(_HEADER_NAME, raw_key)
    fingerprint = compute_auth_signals(ctx)[1]
    assert fingerprint is not None
    assert fingerprint != raw_key
    assert raw_key not in fingerprint


def test_fingerprint_prefix_actually_participates(monkeypatch):
    """The result must differ from a hash computed without the domain-separation prefix."""
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    raw_key = "client-key-789"
    ctx = _ctx_with_header(_HEADER_NAME, raw_key)
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
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_signals(ctx) == ("client", _expected_fingerprint("client-key-123"))


def test_auth_signals_malformed_returns_none_and_no_fingerprint(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_malformed_header(_HEADER_NAME, "bad\nkey")
    assert compute_auth_signals(ctx) == ("none", None)


def test_auth_signals_absent_with_server_key_returns_server_and_server_hash(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_signals(ctx) == ("server", _expected_fingerprint("server-key"))


def test_auth_signals_absent_with_no_server_key_returns_none_and_no_fingerprint(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_signals(ctx) == ("none", None)


# ===========================================================================
# include_server_fingerprint gate — server hash only when a consumer exists
# ===========================================================================
#
# The server-key fingerprint's only consumer is the community usage report, so
# resolve_auth_signals passes include_server_fingerprint=False when community
# reporting is disabled. Only the absent-client / server-key branch is gated;
# the client-key path is deliberately never gated (pre-provisioning for the
# deferred distinct_id follow-up).


def test_auth_signals_absent_with_server_key_skips_server_hash_when_gated(monkeypatch):
    """Absent client key + server key + include_server_fingerprint=False -> ("server", None).

    Origin stays "server"; only the SHA-256 is skipped because nothing consumes it.
    """
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_signals(ctx, include_server_fingerprint=False) == ("server", None)


def test_auth_signals_valid_client_hash_not_gated_by_server_flag(monkeypatch):
    """A valid client key still yields ("client", <client hash>) even with the flag False.

    include_server_fingerprint gates only the server-key branch; the client-key
    fingerprint is preserved as pre-provisioning for the deferred identity work.
    """
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_signals(ctx, include_server_fingerprint=False) == (
        "client",
        _expected_fingerprint("client-key-123"),
    )


def test_compute_auth_signals_skips_server_hash_when_gated_off(monkeypatch):
    """With ``include_server_fingerprint=False`` the server branch derives the origin
    WITHOUT computing the server-key SHA-256.

    Pins the optimization: on the absent-client / configured-server-key branch,
    ``_fingerprint_pro_api_key`` must never be called when the flag is False. If a
    future change drops the gate, the spy below records a call and this test fails.
    """
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)

    fingerprint_spy = MagicMock(side_effect=pro_api_key_context._fingerprint_pro_api_key)
    monkeypatch.setattr(pro_api_key_context, "_fingerprint_pro_api_key", fingerprint_spy)

    ctx = _ctx_with_header(_HEADER_NAME, "")  # absent client key -> server fallback
    assert compute_auth_signals(ctx, include_server_fingerprint=False) == ("server", None)
    fingerprint_spy.assert_not_called()
