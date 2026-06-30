# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the ctx-derived auth-origin and fingerprint helpers.

Kept in a focused sibling module rather than grown into
``tests/test_pro_api_key_context.py`` (already 466 LOC, close to the rule
``210`` 500-LOC limit) per the rule ``210`` guidance.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from starlette.datastructures import Headers

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import PRO_API_KEY_HASH_PREFIX
from blockscout_mcp_server.pro_api_key_context import (
    compute_api_key_fingerprint,
    compute_auth_origin,
)

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
# compute_auth_origin
# ===========================================================================


def test_auth_origin_valid_client_header_is_client(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_origin(ctx) == "client"


def test_auth_origin_malformed_header_is_none(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_malformed_header(_HEADER_NAME, "bad\nkey")
    assert compute_auth_origin(ctx) == "none"


def test_auth_origin_malformed_over_length_header_is_none(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_malformed_header(_HEADER_NAME, "a" * 257)
    assert compute_auth_origin(ctx) == "none"


def test_auth_origin_absent_header_with_server_key_is_server(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_origin(ctx) == "server"


def test_auth_origin_absent_header_with_no_server_key_is_none(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_auth_origin(ctx) == "none"


def test_auth_origin_feature_disabled_with_server_key_is_server(monkeypatch):
    """Header feature disabled (empty header config) + server key configured -> server.

    "Feature disabled" alone does not force "none" -- a disabled header feature
    makes the extractor return _Absent, which falls through to the server-key
    branch just like a genuinely absent header.
    """
    monkeypatch.setattr(config, "pro_api_key_header", "", raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_origin(ctx) == "server"


def test_auth_origin_feature_disabled_with_no_server_key_is_none(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "", raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_origin(ctx) == "none"


# ===========================================================================
# compute_api_key_fingerprint
# ===========================================================================


def test_fingerprint_valid_client_header_matches_expected_hash(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_api_key_fingerprint(ctx) == _expected_fingerprint("client-key-123")


def test_fingerprint_absent_header_with_server_key_matches_expected_hash(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_api_key_fingerprint(ctx) == _expected_fingerprint("server-key")


def test_fingerprint_malformed_header_is_none(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_malformed_header(_HEADER_NAME, "bad\nkey")
    assert compute_api_key_fingerprint(ctx) is None


def test_fingerprint_absent_header_with_no_server_key_is_none(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "")
    assert compute_api_key_fingerprint(ctx) is None


# ===========================================================================
# No-fallback precedence (competing server key configured)
# ===========================================================================
#
# These cases set config.pro_api_key = "server-key" so a server-fallback
# regression cannot hide: a valid client header must still win, and a
# malformed client header must still yield no usable key (no silent fallback
# to the configured server key). Mirrors the precedence already enforced by
# resolve_pro_api_key(). Kept distinct from the absent-header cases above,
# which deliberately exercise the server branch.


def test_auth_origin_valid_client_header_wins_over_configured_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    assert compute_auth_origin(ctx) == "client"


def test_fingerprint_valid_client_header_wins_over_configured_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_header(_HEADER_NAME, "client-key-123")
    fingerprint = compute_api_key_fingerprint(ctx)
    assert fingerprint == _expected_fingerprint("client-key-123")
    assert fingerprint != _expected_fingerprint("server-key")


def test_auth_origin_malformed_client_header_does_not_fall_back_to_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_malformed_header(_HEADER_NAME, "bad\nkey")
    assert compute_auth_origin(ctx) == "none"


def test_fingerprint_malformed_client_header_does_not_fall_back_to_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    ctx = _ctx_with_malformed_header(_HEADER_NAME, "bad\nkey")
    assert compute_api_key_fingerprint(ctx) is None


# ===========================================================================
# Fingerprint safety: raw key never leaks; prefix actually participates
# ===========================================================================


def test_fingerprint_never_equals_or_contains_raw_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    raw_key = "super-secret-client-key-456"
    ctx = _ctx_with_header(_HEADER_NAME, raw_key)
    fingerprint = compute_api_key_fingerprint(ctx)
    assert fingerprint is not None
    assert fingerprint != raw_key
    assert raw_key not in fingerprint


def test_fingerprint_prefix_actually_participates(monkeypatch):
    """The result must differ from a hash computed without the domain-separation prefix."""
    monkeypatch.setattr(config, "pro_api_key_header", _HEADER_NAME, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    raw_key = "client-key-789"
    ctx = _ctx_with_header(_HEADER_NAME, raw_key)
    fingerprint = compute_api_key_fingerprint(ctx)
    unprefixed_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    assert fingerprint != unprefixed_hash
