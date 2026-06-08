# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the @pro_api_credit_scope decorator.

Covers the AST-based coverage guard (every @pro_api_key_scope tool also
carries @pro_api_credit_scope as an inner decorator), fresh sink per
invocation, ContextVar reset on return/exception, sequential-invocation
isolation, transport-agnosticism, and functools.wraps metadata preservation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from blockscout_mcp_server.api.dependencies import MockCtx
from blockscout_mcp_server.pro_api_key_context import CreditSink, _credit_sink, pro_api_credit_scope

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
