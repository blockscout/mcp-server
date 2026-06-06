# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for credit capture core and the @pro_api_credit_scope decorator.

Phase 2: credit-capture core (header capture, minimum semantics, cross-task
visibility via the shared CreditSink mutable box).

Phase 3: decorator tests — @pro_api_credit_scope decorator coverage guard
(AST-based), fresh sink per invocation, ContextVar reset on return/exception,
invocation isolation, and transport-agnosticism.

Tests validate:
- Header capture into the CreditSink.
- Minimum-value semantics.
- Case-insensitive header lookup.
- No capture on missing/unparseable/non-str header values.
- Mock-typed header guard (regression for float(MagicMock()) == 1.0).
- Negative value capture (overdrawn paid account).
- No-sink silent no-op.
- Cross-task visibility via make_request_with_periodic_progress and asyncio.gather.
- All three public helper surfaces (GET, POST, metadata) route through the
  shared capture point.

Import CreditSink and _credit_sink from their canonical home:
blockscout_mcp_server.pro_api_key_context (not tools.common).
"""

from __future__ import annotations

import ast
import asyncio
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.api.dependencies import MockCtx
from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import CreditSink, _credit_sink, pro_api_credit_scope

# ---------------------------------------------------------------------------
# Test-isolation helper: set the ContextVar directly and always reset it.
# Mirrors the discipline in tests/test_pro_api_key_context.py.
# ---------------------------------------------------------------------------


@contextmanager
def _set_sink(sink: CreditSink | None):
    """Context manager that sets _credit_sink and resets it in finally."""
    token = _credit_sink.set(sink)
    try:
        yield
    finally:
        _credit_sink.reset(token)


# ---------------------------------------------------------------------------
# Shared mock helpers (mirrors test_common_post_request.py and
# test_common_metadata.py patterns).
# ---------------------------------------------------------------------------


class _MockResponse:
    """Minimal fake httpx response for GET/POST helpers."""

    def __init__(self, json_data=None, status_code=200, headers=None):
        self._json_data = json_data
        self.status_code = status_code
        self.reason_phrase = "OK"
        self.request = httpx.Request("GET", "https://api.blockscout.com/1/x")
        self.text = ""
        self.headers = headers if headers is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=self)

    def json(self):
        return self._json_data


class _SimpleClient:
    """Async context-manager client that returns a fixed response."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        return self._response

    async def post(self, url, json, params, headers=None, **kwargs):
        return self._response


# ---------------------------------------------------------------------------
# CreditSink unit tests
# ---------------------------------------------------------------------------


def test_credit_sink_first_observation_sets_value():
    sink = CreditSink()
    assert sink.remaining is None
    sink.record(5000.0)
    assert sink.remaining == 5000.0


def test_credit_sink_minimum_semantics_lower_second():
    """6000 then 4000 → 4000 (lower second value wins)."""
    sink = CreditSink()
    sink.record(6000.0)
    sink.record(4000.0)
    assert sink.remaining == 4000.0


def test_credit_sink_minimum_semantics_higher_second():
    """4000 then 6000 → 4000 (minimum is retained)."""
    sink = CreditSink()
    sink.record(4000.0)
    sink.record(6000.0)
    assert sink.remaining == 4000.0


def test_credit_sink_negative_value_captured():
    """Negative values (overdrawn paid account) are stored as-is."""
    sink = CreditSink()
    sink.record(-12.5)
    assert sink.remaining == -12.5


def test_credit_sink_negative_beats_positive():
    """A later negative value lowers the stored minimum below zero."""
    sink = CreditSink()
    sink.record(100.0)
    sink.record(-5.0)
    assert sink.remaining == -5.0


# ---------------------------------------------------------------------------
# _capture_credits_remaining via make_blockscout_request (GET path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_request_captures_credits_remaining():
    """A successful GET response whose headers carry x-credits-remaining records the value."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "4200"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining == 4200.0


@pytest.mark.asyncio
async def test_get_request_missing_header_sink_stays_none():
    """A response without x-credits-remaining leaves the sink at None."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining is None


@pytest.mark.asyncio
async def test_get_request_unparseable_header_sink_stays_none():
    """A non-numeric x-credits-remaining header leaves the sink at None."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "not-a-number"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining is None


@pytest.mark.asyncio
async def test_get_request_mock_typed_header_no_capture():
    """A MagicMock headers object must not produce a capture (regression guard).

    Without the isinstance(value, str) guard, float(MagicMock()) returns 1.0
    because MagicMock implements __float__, which would surface a false
    low-credits note.  This test pins the guard in place.
    """
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    # response.headers is a MagicMock — get_header_case_insensitive will call
    # headers.get(...) which returns a child MagicMock (not a str).
    mock_headers = MagicMock()
    response = _MockResponse({"data": "ok"}, headers={})
    response.headers = mock_headers

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    # Sink must stay None — no bogus 1.0 capture.
    assert sink.remaining is None


@pytest.mark.asyncio
async def test_get_request_no_sink_in_context_is_silent_noop():
    """With no sink established (_credit_sink is None), the request succeeds without error."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "9999"})

    # _credit_sink is None by default — do not set a sink.
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(config, "pro_api_key", "test_key"),
    ):
        result = await make_blockscout_request("1", "/api/v2/blocks/1")

    assert result == {"data": "ok"}


@pytest.mark.asyncio
async def test_get_request_case_insensitive_header_lookup():
    """x-credits-remaining is captured regardless of the header's casing."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    # Plain dict with a mixed-case key — proves get_header_case_insensitive is used.
    response = _MockResponse({"data": "ok"}, headers={"X-Credits-Remaining": "4200"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining == 4200.0


@pytest.mark.asyncio
async def test_get_request_negative_value_captured():
    """A negative x-credits-remaining (overdrawn paid account) is captured as-is."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "-12.5"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining == -12.5


# ---------------------------------------------------------------------------
# Parameterized: all three public helper surfaces route through capture
# ---------------------------------------------------------------------------


class _PostClient:
    """Async context-manager client for POST calls."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json, params, headers=None, **kwargs):
        return self._response


class _GetClient:
    """Async context-manager client for GET calls."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        return self._response


HELPER_IDS = ["make_blockscout_request", "make_blockscout_post_request", "make_metadata_request"]


@pytest.mark.asyncio
@pytest.mark.parametrize("helper_name", HELPER_IDS)
async def test_all_helper_surfaces_capture_credits_remaining(helper_name):
    """GET, POST, and metadata helpers all record x-credits-remaining into the sink.

    This pins the 'single capture point covers all helpers' guarantee: because
    make_blockscout_request, make_blockscout_post_request, and make_metadata_request
    all delegate to _make_blockscout_http_request, a single capture call there
    covers all three surfaces without per-helper logic.
    """
    from blockscout_mcp_server.tools import common as common_module

    credits_header = {"x-credits-remaining": "7777"}

    if helper_name == "make_blockscout_request":
        response = _MockResponse({"ok": True}, headers=credits_header)
        client = _GetClient(response)
        call_kwargs = {
            "request_function": common_module.make_blockscout_request,
            "call_args": {"chain_id": "1", "api_path": "/api/v2/blocks/1"},
            "client_patch": client,
            "method": "get",
        }
    elif helper_name == "make_blockscout_post_request":
        response = _MockResponse({"ok": True}, headers=credits_header)
        client = _PostClient(response)
        call_kwargs = {
            "request_function": common_module.make_blockscout_post_request,
            "call_args": {"chain_id": "1", "api_path": "/json-rpc", "json_body": {"x": 1}},
            "client_patch": client,
            "method": "post",
        }
    else:  # make_metadata_request
        request = httpx.Request("GET", "https://api.blockscout.com/metadata")
        real_response = httpx.Response(200, json={"ok": True}, request=request, headers=credits_header)

        class _MetaClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, url, **kwargs):
                return real_response

        client = _MetaClient()
        call_kwargs = {
            "request_function": common_module.make_metadata_request,
            "call_args": {"api_path": "/api/v1/metadata/address"},
            "client_patch": client,
            "method": "get",
        }

    sink = CreditSink()

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=call_kwargs["client_patch"]),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await call_kwargs["request_function"](**call_kwargs["call_args"])

    assert sink.remaining == 7777.0, f"{helper_name} did not capture credits"


# ---------------------------------------------------------------------------
# Cross-task visibility: make_request_with_periodic_progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_task_visibility_via_periodic_progress(mock_ctx):
    """Credit captured in a child task spawned by make_request_with_periodic_progress is visible to the parent.

    make_request_with_periodic_progress uses an anyio task group internally.
    The child task runs in a copied context, but shares the same CreditSink
    object reference, so mutations are visible to the parent.
    """
    from blockscout_mcp_server.tools.common import make_blockscout_request, make_request_with_periodic_progress

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "3333"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            result = await make_request_with_periodic_progress(
                ctx=mock_ctx,
                request_function=make_blockscout_request,
                request_args={"chain_id": "1", "api_path": "/api/v2/blocks/1"},
                total_duration_hint=30.0,
            )

    assert result == {"data": "ok"}
    # The value written by the child task must be visible on the parent's sink.
    assert sink.remaining == 3333.0


# ---------------------------------------------------------------------------
# Cross-task visibility: asyncio.gather (two concurrent requests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_task_visibility_via_asyncio_gather():
    """Concurrent requests via asyncio.gather both write to the shared sink; minimum is recorded.

    Two concurrent GET requests return different x-credits-remaining values.
    The sink must end up with the minimum of the two.
    """
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()

    response_high = _MockResponse({"seq": "high"}, headers={"x-credits-remaining": "9000"})
    response_low = _MockResponse({"seq": "low"}, headers={"x-credits-remaining": "2000"})
    responses = [response_high, response_low]
    call_count = {"n": 0}

    class _AlternatingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx % len(responses)]

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_AlternatingClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            results = await asyncio.gather(
                make_blockscout_request("1", "/api/v2/blocks/1"),
                make_blockscout_request("1", "/api/v2/blocks/2"),
            )

    assert len(results) == 2
    # Minimum of 9000 and 2000 must be recorded.
    assert sink.remaining == 2000.0


# ===========================================================================
# Phase 3: @pro_api_credit_scope decorator tests
# ===========================================================================

TOOLS_ROOT = Path(__file__).parent.parent.parent / "blockscout_mcp_server" / "tools"


def _decorator_names(decorator_list: list[ast.expr]) -> list[str]:
    """Return decorator names in source order (outermost first) for a decorator_list."""
    names: list[str] = []
    for node in decorator_list:
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return names


# ---------------------------------------------------------------------------
# AST coverage guard
# ---------------------------------------------------------------------------


def test_pro_api_credit_scope_applied_to_all_scoped_tools() -> None:
    """Every function decorated with @pro_api_key_scope must also have
    @pro_api_credit_scope immediately inside it (appearing after in source
    order).  Driving discovery off the existing @pro_api_key_scope means this
    guard automatically covers any tool added later."""
    tool_py_files = list(TOOLS_ROOT.rglob("*.py"))

    violations: list[str] = []
    decorated_count = 0

    for path in tool_py_files:
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            dec_names = _decorator_names(node.decorator_list)

            if "pro_api_key_scope" not in dec_names:
                continue

            decorated_count += 1

            if "pro_api_credit_scope" not in dec_names:
                violations.append(
                    f"{path.relative_to(TOOLS_ROOT.parent.parent)}:"
                    f"{node.lineno}: {node.name} has @pro_api_key_scope but not @pro_api_credit_scope"
                )
                continue

            key_idx = dec_names.index("pro_api_key_scope")
            credit_idx = dec_names.index("pro_api_credit_scope")
            if credit_idx <= key_idx:
                violations.append(
                    f"{path.relative_to(TOOLS_ROOT.parent.parent)}:"
                    f"{node.lineno}: {node.name}: @pro_api_credit_scope must appear "
                    f"*after* @pro_api_key_scope in source (inner decorator), "
                    f"but found key_scope at index {key_idx}, credit_scope at index {credit_idx}"
                )

    assert decorated_count > 0, "No @pro_api_key_scope-decorated functions found — discovery logic is broken"
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# Fresh sink per invocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credit_scope_establishes_fresh_sink() -> None:
    """Invoking a function wrapped with @pro_api_credit_scope causes
    _credit_sink.get() to return a fresh CreditSink (not None) inside the body."""
    sink_inside: CreditSink | None = None

    @pro_api_credit_scope
    async def stub_tool() -> None:
        nonlocal sink_inside
        sink_inside = _credit_sink.get()

    await stub_tool()

    assert sink_inside is not None
    assert isinstance(sink_inside, CreditSink)


# ---------------------------------------------------------------------------
# ContextVar reset on normal return
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credit_scope_resets_context_var_after_return() -> None:
    """After the call completes normally the ContextVar is reset to its prior
    value (default None)."""
    # Confirm we start with the default
    assert _credit_sink.get() is None

    @pro_api_credit_scope
    async def stub_tool() -> None:
        pass

    await stub_tool()

    assert _credit_sink.get() is None


# ---------------------------------------------------------------------------
# ContextVar reset on exception (finally discipline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credit_scope_resets_context_var_after_exception() -> None:
    """The ContextVar is reset even when the wrapped function raises."""

    @pro_api_credit_scope
    async def failing_tool() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await failing_tool()

    assert _credit_sink.get() is None


# ---------------------------------------------------------------------------
# Isolation between sequential invocations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credit_scope_isolates_sequential_invocations() -> None:
    """A value recorded in the first invocation's sink must not be visible
    at the start of the second invocation."""
    sinks: list[CreditSink] = []

    @pro_api_credit_scope
    async def stub_tool() -> None:
        sink = _credit_sink.get()
        assert sink is not None
        sinks.append(sink)
        sink.record(50.0)

    await stub_tool()
    await stub_tool()

    # Each invocation saw a distinct CreditSink object
    assert len(sinks) == 2
    assert sinks[0] is not sinks[1]
    # The second invocation started fresh (its sink was empty before record)
    assert sinks[1].remaining == 50.0
    # Both independently recorded the same value
    assert sinks[0].remaining == 50.0


# ---------------------------------------------------------------------------
# Transport-agnostic: REST context still gets a fresh sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credit_scope_transport_agnostic_rest_context() -> None:
    """Invoking the decorated stub with a REST-style MockCtx still establishes
    a fresh sink — the decorator reads nothing from ctx."""
    sink_inside: CreditSink | None = None

    @pro_api_credit_scope
    async def stub_tool(ctx: object) -> None:
        nonlocal sink_inside
        sink_inside = _credit_sink.get()

    rest_ctx = MockCtx()
    assert rest_ctx.call_source == "rest"

    await stub_tool(ctx=rest_ctx)

    assert sink_inside is not None
    assert isinstance(sink_inside, CreditSink)
    # After the call the ContextVar is back to None (REST transport is no different)
    assert _credit_sink.get() is None


# ---------------------------------------------------------------------------
# functools.wraps preserves the wrapped function's name and signature
# ---------------------------------------------------------------------------


def test_credit_scope_preserves_function_metadata() -> None:
    """@pro_api_credit_scope uses functools.wraps so FastMCP schema generation
    and REST parameter binding continue to work."""

    @pro_api_credit_scope
    async def my_named_tool(a: int, b: str) -> str:
        return b * a

    assert my_named_tool.__name__ == "my_named_tool"
    assert my_named_tool.__wrapped__ is not None  # type: ignore[attr-defined]


# ===========================================================================
# Phase 4: build_tool_response low-credits advisory note
# ===========================================================================


def test_build_tool_response_note_present_below_threshold():
    """Advisory note appears when the sink's remaining value is below the threshold."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(4999.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert len(response.notes) == 1
    assert "4999" in response.notes[0]
    assert "5000" in response.notes[0]
    assert "https://dev.blockscout.com" in response.notes[0]


def test_build_tool_response_note_absent_at_threshold():
    """No advisory note when remaining equals the threshold (not strictly below)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(5000.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_absent_above_threshold():
    """No advisory note when remaining is well above the threshold."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(9000.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_present_for_zero_balance():
    """Advisory note appears when remaining is exactly zero."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(0.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert len(response.notes) == 1
    assert "0" in response.notes[0]


def test_build_tool_response_note_present_for_negative_balance():
    """Advisory note appears when remaining is negative (overdrawn paid account)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(-50.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    assert len(response.notes) == 1
    assert "-50" in response.notes[0]


def test_build_tool_response_note_absent_when_threshold_disabled():
    """No advisory note when threshold is 0 (feature disabled), even with a low balance."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(100.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 0):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_absent_when_no_sink():
    """No advisory note when there is no sink in context (_credit_sink is None)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    # _credit_sink defaults to None — do not set a sink
    assert _credit_sink.get() is None
    response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_absent_when_sink_has_no_value():
    """No advisory note when a sink exists but never captured a value (remaining is None)."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    # Do not call sink.record() — remaining stays None

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is None


def test_build_tool_response_note_coexists_with_caller_notes():
    """Advisory note is appended to caller-supplied notes without mutating the original list."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(100.0)

    original_notes = ["existing note"]

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True}, notes=original_notes)

    # Original list must not be mutated
    assert original_notes == ["existing note"]

    assert response.notes is not None
    assert len(response.notes) == 2
    assert response.notes[0] == "existing note"
    assert "https://dev.blockscout.com" in response.notes[1]


def test_build_tool_response_note_coexists_with_pagination_instructions():
    """Advisory note in notes does not disturb auto-appended pagination instructions."""
    from blockscout_mcp_server.models import NextCallInfo, PaginationInfo
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(1000.0)

    pagination = PaginationInfo(
        next_call=NextCallInfo(tool_name="get_block_info", params={"chain_id": "1", "cursor": "abc"})
    )

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True}, pagination=pagination)

    # Advisory note must appear in notes
    assert response.notes is not None
    assert any("https://dev.blockscout.com" in n for n in response.notes)

    # Pagination instructions must be present
    assert response.instructions is not None
    assert any("MORE DATA AVAILABLE" in i for i in response.instructions)


def test_build_tool_response_integer_display_for_whole_number():
    """Remaining balance is displayed as an integer (4999, not 4999.0) when it is whole."""
    from blockscout_mcp_server.tools.common import build_tool_response

    sink = CreditSink()
    sink.record(4999.0)

    with _set_sink(sink):
        with patch.object(config, "pro_api_low_credits_threshold", 5000):
            response = build_tool_response(data={"ok": True})

    assert response.notes is not None
    note = response.notes[0]
    assert "4999 credits" in note
    assert "4999.0" not in note


# ===========================================================================
# Phase 5: Cross-mode end-to-end note (MCP + REST)
# ===========================================================================


@pytest.mark.asyncio
async def test_mcp_mode_low_credits_note_in_tool_response(mock_ctx):
    """MCP mode: decorated get_block_number call with a low x-credits-remaining
    produces a ToolResponse whose notes contain the low-credits advisory.

    This exercises the full chain:
      @pro_api_credit_scope decorator (establishes sink)
      → make_blockscout_request (captures header into sink)
      → build_tool_response (reads sink and emits advisory note)
    """
    from blockscout_mcp_server.tools.block.get_block_number import get_block_number

    # Response that looks like the /api/v2/main-page/blocks payload.
    block_payload = [{"height": 21000000, "timestamp": "2025-01-01T00:00:00.000000Z"}]
    # x-credits-remaining is below the default threshold of 5000.
    response = _MockResponse(block_payload, headers={"x-credits-remaining": "4200"})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(config, "pro_api_key", "test_key"),
        patch.object(config, "pro_api_low_credits_threshold", 5000),
    ):
        result = await get_block_number(chain_id="1", ctx=mock_ctx)

    assert result.notes is not None
    assert any("4200" in note for note in result.notes)
    assert any("https://dev.blockscout.com" in note for note in result.notes)


@pytest.mark.asyncio
async def test_mcp_mode_healthy_credits_no_note_in_tool_response(mock_ctx):
    """MCP mode: same call with a healthy balance (at or above threshold) yields no advisory note."""
    from blockscout_mcp_server.tools.block.get_block_number import get_block_number

    block_payload = [{"height": 21000000, "timestamp": "2025-01-01T00:00:00.000000Z"}]
    # x-credits-remaining is at the threshold — not strictly below, so no note.
    response = _MockResponse(block_payload, headers={"x-credits-remaining": "5000"})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(config, "pro_api_key", "test_key"),
        patch.object(config, "pro_api_low_credits_threshold", 5000),
    ):
        result = await get_block_number(chain_id="1", ctx=mock_ctx)

    # notes should be None (no advisory, no caller-supplied notes)
    assert result.notes is None
