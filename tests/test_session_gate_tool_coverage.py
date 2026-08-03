# SPDX-License-Identifier: LicenseRef-Blockscout
"""Completeness check: every registered MCP tool actually enforces the session gate.

`tests/test_tool_descriptions.py` proves every tool's *schema* carries the
`session_id` parameter; this module proves the *behavior*: with the gate enabled,
invoking any registered tool except `__unlock_blockchain_analysis__` (the sole
issuer of identifiers) without a `session_id` must be refused with
`SessionIdMissingError` before the tool body runs. A future tool that adds the
parameter (to satisfy the schema test) but forgets the `@session_gate` /
`@session_gate_unmetered` decorator fails here instead of shipping ungated.

Enumeration goes through the FastMCP tool registry (`mcp._tool_manager` — private,
but the only surface that pairs each registered tool with its callable), so a new
tool is covered the moment it is registered, with no per-tool list to maintain.
"""

import inspect

import pytest

from blockscout_mcp_server import server
from blockscout_mcp_server.session_gate import SessionIdMissingError

UNLOCK_TOOL_NAME = "__unlock_blockchain_analysis__"


@pytest.mark.asyncio
async def test_every_registered_tool_refuses_calls_without_session_id(enabled_session_gate, mock_ctx):
    tools = server.mcp._tool_manager.list_tools()
    assert tools, "No tools registered — tool discovery is broken"
    assert any(tool.name == UNLOCK_TOOL_NAME for tool in tools)

    ungated: list[str] = []
    for tool in tools:
        if tool.name == UNLOCK_TOOL_NAME:
            continue

        # The gate refuses before the tool body runs, so required parameters only
        # need to *bind* — placeholder values never reach validation or upstream I/O.
        kwargs = {}
        for name, param in inspect.signature(tool.fn).parameters.items():
            if name == "ctx":
                kwargs[name] = mock_ctx
            elif param.default is inspect.Parameter.empty:
                kwargs[name] = "placeholder"

        try:
            await tool.fn(**kwargs)
        except SessionIdMissingError:
            continue
        except Exception as exc:  # noqa: BLE001 — any other outcome means the gate did not run first
            ungated.append(f"{tool.name}: raised {type(exc).__name__} instead of SessionIdMissingError")
        else:
            ungated.append(f"{tool.name}: served without a session_id")

    assert not ungated, "Tools not enforcing the session gate:\n" + "\n".join(ungated)
