# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for blockscout_mcp_server.pro_api_key_context."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from starlette.datastructures import Headers

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import (
    _Absent,
    _client_key_state,
    _Malformed,
    _normalize_key,
    _Valid,
    extract_client_pro_api_key_from_ctx,
    pro_api_key_scope,
    resolve_pro_api_key,
)

# ---------------------------------------------------------------------------
# Test-isolation helper: set the ContextVar directly and always reset it.
# Exercising state through @pro_api_key_scope is inherently safe (the decorator
# already resets its own token).  Only direct-set tests need this helper.
# ---------------------------------------------------------------------------


@contextmanager
def _set_key_state(state):
    """Context manager that sets _client_key_state and resets it in finally."""
    token = _client_key_state.set(state)
    try:
        yield
    finally:
        _client_key_state.reset(token)


# ===========================================================================
# Normalization / validation
# ===========================================================================


def test_normalize_plain_value_is_valid():
    state = _normalize_key("abc-123")
    assert isinstance(state, _Valid)
    assert state.value == "abc-123"


def test_normalize_strips_whitespace():
    state = _normalize_key("  my-key  ")
    assert isinstance(state, _Valid)
    assert state.value == "my-key"


def test_normalize_empty_string_is_absent():
    assert isinstance(_normalize_key(""), _Absent)


def test_normalize_blank_string_is_absent():
    assert isinstance(_normalize_key("   "), _Absent)


def test_normalize_non_string_mock_is_absent():
    assert isinstance(_normalize_key(MagicMock()), _Absent)


def test_normalize_non_string_int_is_absent():
    assert isinstance(_normalize_key(42), _Absent)


def test_normalize_control_char_newline_is_malformed():
    state = _normalize_key("valid-prefix\ninjected")
    assert isinstance(state, _Malformed)


def test_normalize_control_char_carriage_return_is_malformed():
    state = _normalize_key("key\r\ninjection")
    assert isinstance(state, _Malformed)


def test_normalize_control_char_tab_is_malformed():
    state = _normalize_key("key\twith-tab")
    assert isinstance(state, _Malformed)


def test_normalize_control_char_del_is_malformed():
    state = _normalize_key("key\x7f")
    assert isinstance(state, _Malformed)


def test_normalize_over_length_is_malformed():
    state = _normalize_key("a" * 257)
    assert isinstance(state, _Malformed)


def test_normalize_exactly_max_length_is_valid():
    state = _normalize_key("a" * 256)
    assert isinstance(state, _Valid)


# ===========================================================================
# Extraction scoping
# ===========================================================================


def _mcp_ctx_with_header(header_name: str, header_value: str) -> SimpleNamespace:
    """Build a minimal MCP-like context carrying *header_value* under *header_name*.

    Uses real ``starlette.datastructures.Headers`` with non-canonical casing to
    exercise case-insensitive lookup.
    """
    # Use non-canonical casing to prove case-insensitive lookup works.
    # starlette.datastructures.Headers accepts a Mapping (dict) for the headers param.
    headers = Headers(headers={header_name.upper(): header_value})
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def test_extraction_rest_call_source_is_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    ctx = _mcp_ctx_with_header("Blockscout-MCP-Pro-Api-Key", "client-key-123")
    ctx.call_source = "rest"  # type: ignore[attr-defined]
    assert isinstance(extract_client_pro_api_key_from_ctx(ctx), _Absent)


def test_extraction_empty_header_config_is_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "", raising=False)
    ctx = _mcp_ctx_with_header("Blockscout-MCP-Pro-Api-Key", "client-key-123")
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
    # Pass the header under ALL-CAPS to prove case-insensitive lookup.
    # starlette.datastructures.Headers accepts a Mapping (dict) for the headers param.
    headers = Headers(headers={"BLOCKSCOUT-MCP-PRO-API-KEY": "my-client-key"})
    request = SimpleNamespace(headers=headers)
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))

    state = extract_client_pro_api_key_from_ctx(ctx)
    assert isinstance(state, _Valid)
    assert state.value == "my-client-key"


def test_extraction_defensive_on_unexpected_ctx():
    """An entirely unexpected context shape must return absent, not raise."""
    state = extract_client_pro_api_key_from_ctx(object())
    assert isinstance(state, _Absent)


# ===========================================================================
# Resolution precedence matrix
# ===========================================================================


def test_resolve_client_valid_returns_client_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    with _set_key_state(_Valid(value="client-key")):
        assert resolve_pro_api_key() == "client-key"


def test_resolve_absent_with_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    with _set_key_state(_Absent()):
        assert resolve_pro_api_key() == "server-key"


def test_resolve_absent_with_empty_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    with _set_key_state(_Absent()):
        assert resolve_pro_api_key() == ""


def test_resolve_malformed_raises_value_error(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    with _set_key_state(_Malformed()):
        with pytest.raises(ValueError):
            resolve_pro_api_key()


def test_resolve_malformed_does_not_fall_back_to_server_key(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    with _set_key_state(_Malformed()):
        with pytest.raises(ValueError) as exc_info:
            resolve_pro_api_key()
        # Error message must mention client-supplied key being malformed
        assert "malformed" in str(exc_info.value).lower()


# ===========================================================================
# Secret redaction in the malformed error
# ===========================================================================


def test_malformed_error_does_not_embed_control_char_value(monkeypatch):
    """ValueError message must not reproduce the raw submitted value."""
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    raw_value = "key-with\ncontrol-char"
    with _set_key_state(_Malformed()):
        with pytest.raises(ValueError) as exc_info:
            resolve_pro_api_key()
        assert raw_value not in str(exc_info.value)


def test_malformed_error_does_not_embed_over_length_value(monkeypatch):
    """ValueError message must not reproduce an over-length submitted value."""
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    raw_value = "a" * 257
    with _set_key_state(_Malformed()):
        with pytest.raises(ValueError) as exc_info:
            resolve_pro_api_key()
        assert raw_value not in str(exc_info.value)


# ===========================================================================
# Decorator behaviour
# ===========================================================================


def _ctx_with_starlette_headers(header_name: str, header_value: str) -> SimpleNamespace:
    """Build an MCP-like context using real starlette.datastructures.Headers (dict form).

    The header name is passed in UPPER CASE so the case-insensitive lookup is exercised.
    """
    headers = Headers(headers={header_name.upper(): header_value})
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


@pytest.mark.asyncio
async def test_decorator_sets_valid_state_during_call(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    observed_state: list[object] = []

    @pro_api_key_scope
    async def dummy(ctx) -> None:
        observed_state.append(_client_key_state.get())

    ctx = _ctx_with_starlette_headers("Blockscout-MCP-Pro-Api-Key", "client-key-xyz")

    await dummy(ctx=ctx)

    assert len(observed_state) == 1
    assert isinstance(observed_state[0], _Valid)
    assert observed_state[0].value == "client-key-xyz"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_decorator_resets_state_after_call(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    @pro_api_key_scope
    async def dummy(ctx) -> None:
        pass

    ctx = _ctx_with_starlette_headers("Blockscout-MCP-Pro-Api-Key", "client-key-xyz")

    await dummy(ctx=ctx)

    # After the call, the state should be back to the default (_Absent)
    assert isinstance(_client_key_state.get(), _Absent)


@pytest.mark.asyncio
async def test_decorator_resets_state_even_when_wrapped_function_raises(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    @pro_api_key_scope
    async def dummy(ctx) -> None:
        raise RuntimeError("boom")

    ctx = _ctx_with_starlette_headers("Blockscout-MCP-Pro-Api-Key", "client-key-xyz")

    with pytest.raises(RuntimeError, match="boom"):
        await dummy(ctx=ctx)

    # State must be reset even after an exception
    assert isinstance(_client_key_state.get(), _Absent)


@pytest.mark.asyncio
async def test_decorator_rest_call_source_leaves_state_absent(monkeypatch):
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    observed_state: list[object] = []

    @pro_api_key_scope
    async def dummy(ctx) -> None:
        observed_state.append(_client_key_state.get())

    ctx = _ctx_with_starlette_headers("Blockscout-MCP-Pro-Api-Key", "client-key-xyz")
    ctx.call_source = "rest"  # type: ignore[attr-defined]

    await dummy(ctx=ctx)

    assert isinstance(observed_state[0], _Absent)


@pytest.mark.asyncio
async def test_decorator_malformed_does_not_raise_from_decorator(monkeypatch):
    """The decorator must never raise for a malformed key; the wrapped function still runs.

    Uses a plain-dict headers stub because real starlette Headers reject header values
    that contain control characters (latin-1 encoding would raise). The normalization
    helper is responsible for detecting them; we test that via a plain string.
    """
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    ran: list[bool] = []

    @pro_api_key_scope
    async def dummy(ctx) -> None:
        ran.append(True)

    # Use a plain dict so we can inject a control-character value that starlette
    # would refuse to encode — the extractor just calls get_header_case_insensitive
    # which works with any Mapping.
    headers = {"Blockscout-MCP-Pro-Api-Key": "bad\x00key"}
    request = SimpleNamespace(headers=headers)
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))

    # Must not raise at decoration time or call time (malformed raise is in resolve_pro_api_key)
    await dummy(ctx=ctx)
    assert ran == [True]


@pytest.mark.asyncio
async def test_decorator_preserves_wrapped_function_name():
    @pro_api_key_scope
    async def my_tool(ctx) -> None:
        pass

    assert my_tool.__name__ == "my_tool"


# ===========================================================================
# Per-task isolation
# ===========================================================================


@pytest.mark.asyncio
async def test_per_task_isolation(monkeypatch):
    """Two concurrent decorated coroutines, each with a different client key,
    must each observe their own resolved key inside their body.
    """
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)

    results: dict[str, str] = {}

    @pro_api_key_scope
    async def dummy(ctx, task_name: str) -> None:
        # Yield control so the other coroutine can start.
        await asyncio.sleep(0)
        results[task_name] = resolve_pro_api_key()

    def _ctx_with_key(key: str) -> SimpleNamespace:
        headers = Headers(headers={"Blockscout-MCP-Pro-Api-Key": key})
        request = SimpleNamespace(headers=headers)
        return SimpleNamespace(request_context=SimpleNamespace(request=request))

    ctx_a = _ctx_with_key("key-for-task-a")
    ctx_b = _ctx_with_key("key-for-task-b")

    await asyncio.gather(
        dummy(ctx=ctx_a, task_name="a"),
        dummy(ctx=ctx_b, task_name="b"),
    )

    assert results["a"] == "key-for-task-a"
    assert results["b"] == "key-for-task-b"
