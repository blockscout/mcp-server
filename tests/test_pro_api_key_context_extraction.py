# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for extraction scoping in blockscout_mcp_server.pro_api_key_context.

Split out of test_pro_api_key_context.py to keep both files under the 500 LOC
limit (see .cursor/rules/210-unit-testing-guidelines.mdc). Covers
extract_client_pro_api_key_from_ctx: call-source handling, the configured
header, and the x-api-key fallback header.
"""

from __future__ import annotations

from types import SimpleNamespace

from pro_api_key_helpers import (
    ctx_with_header,
    ctx_with_headers,
    ctx_with_malformed_header,
    ctx_with_malformed_headers,
)

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import (
    _Absent,
    _Malformed,
    _Valid,
    extract_client_pro_api_key_from_ctx,
)

# ===========================================================================
# Extraction scoping
# ===========================================================================


def test_extraction_rest_call_source_reads_header(monkeypatch):
    """A REST-source context that carries the configured header must yield _Valid."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_header("Blockscout-MCP-Pro-Api-Key", "client-key-123")
    ctx.call_source = "rest"  # type: ignore[attr-defined]
    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "client-key-123"


def test_extraction_rest_call_source_absent_header_is_absent(monkeypatch):
    """A REST-source context with no header value yields _Absent."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_header("Blockscout-MCP-Pro-Api-Key", "")
    ctx.call_source = "rest"  # type: ignore[attr-defined]
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_rest_call_source_malformed_header_is_malformed(monkeypatch):
    """A REST-source context with a control-char header value yields _Malformed."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_malformed_header("Blockscout-MCP-Pro-Api-Key", "bad\nkey")
    ctx.call_source = "rest"
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Malformed)


def test_extraction_rest_call_source_over_length_header_is_malformed(monkeypatch):
    """A REST-source context with an over-length header value yields _Malformed."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_malformed_header("Blockscout-MCP-Pro-Api-Key", "a" * 257)
    ctx.call_source = "rest"
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Malformed)


def test_extraction_rest_call_source_disabled_feature_is_absent(monkeypatch):
    """Feature disabled (empty header config) → absent even if the header is present."""
    monkeypatch.setattr(config, "pro_api_key_header", "", raising=False)
    ctx = ctx_with_header("Blockscout-MCP-Pro-Api-Key", "client-key-123")
    ctx.call_source = "rest"  # type: ignore[attr-defined]
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_empty_header_config_is_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "", raising=False)
    ctx = ctx_with_header("Blockscout-MCP-Pro-Api-Key", "client-key-123")
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_no_request_context_is_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = SimpleNamespace()  # no request_context attribute
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_none_request_context_is_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = SimpleNamespace(request_context=None)
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_stdio_like_no_request_is_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=None))
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_mcp_ctx_with_valid_header(monkeypatch):
    """Real starlette Headers + non-canonical casing → valid state."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    # ctx_with_header upper-cases the header name, so this exercises case-insensitive lookup.
    ctx = ctx_with_header("Blockscout-MCP-Pro-Api-Key", "my-client-key")

    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "my-client-key"


def test_extraction_fallback_header_only_is_valid(monkeypatch):
    """Only x-api-key present, configured header absent -> _Valid with the fallback value."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_headers({"x-api-key": "fallback-key-123"})
    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "fallback-key-123"


def test_extraction_configured_header_wins_over_fallback(monkeypatch):
    """Both present with different values -> _Valid with the configured header's value."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_headers(
        {
            "Blockscout-MCP-Pro-Api-Key": "configured-key",
            "x-api-key": "fallback-key",
        }
    )
    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "configured-key"


def test_extraction_blank_configured_header_falls_back(monkeypatch):
    """Configured header present but blank, x-api-key valid -> _Valid with the fallback value."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_headers(
        {
            "Blockscout-MCP-Pro-Api-Key": "",
            "x-api-key": "fallback-key",
        }
    )
    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "fallback-key"


def test_extraction_malformed_configured_header_is_terminal(monkeypatch):
    """Configured header malformed (control char), x-api-key valid -> _Malformed (no fallback)."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_malformed_headers(
        {
            "Blockscout-MCP-Pro-Api-Key": "bad\nkey",
            "x-api-key": "fallback-key",
        }
    )
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Malformed)


def test_extraction_fallback_header_only_malformed_is_malformed(monkeypatch):
    """Only x-api-key present and malformed (over-length) -> _Malformed."""
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = ctx_with_malformed_headers({"x-api-key": "a" * 257})
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Malformed)


def test_extraction_disabled_feature_ignores_fallback_header(monkeypatch):
    """config.pro_api_key_header = "", only x-api-key present -> _Absent."""
    monkeypatch.setattr(config, "pro_api_key_header", "", raising=False)
    ctx = ctx_with_headers({"x-api-key": "fallback-key"})
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_configured_header_case_variant_of_fallback_deduplicates(monkeypatch):
    """config.pro_api_key_header == "X-Api-Key" (case variant of the fallback) -> _Valid.

    This is the behavioral check for deduplication; the number of lookups is an
    implementation detail and is not asserted here.
    """
    monkeypatch.setattr(config, "pro_api_key_header", "X-Api-Key", raising=False)
    ctx = ctx_with_headers({"x-api-key": "single-header-value"})
    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "single-header-value"


def test_extraction_defensive_on_unexpected_ctx():
    """An entirely unexpected context shape must return absent, not raise."""
    state = extract_client_pro_api_key_from_ctx(object())
    assert isinstance(state, _Absent)
