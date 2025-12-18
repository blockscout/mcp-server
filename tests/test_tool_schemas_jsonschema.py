"""Regression tests for MCP tool JSON Schemas.

Some MCP clients/providers perform strict JSON Schema validation and reject any
schema node with {"type": "object"} that omits the "properties" key, even when
"additionalProperties" is used to model dict-like objects.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest


def _iter_object_schema_nodes(schema: object, path: str = "$") -> Iterable[tuple[str, dict]]:
    """Yield (path, node) for any dict node that represents a JSON Schema object."""
    if isinstance(schema, dict):
        yield path, schema
        for key, value in schema.items():
            if isinstance(value, (dict, list)):
                yield from _iter_object_schema_nodes(value, f"{path}.{key}")
    elif isinstance(schema, list):
        for idx, item in enumerate(schema):
            if isinstance(item, (dict, list)):
                yield from _iter_object_schema_nodes(item, f"{path}[{idx}]")


@pytest.mark.asyncio
async def test_all_tool_schemas_include_properties_for_object_nodes():
    """Ensure strict clients don't reject our tool schemas.

    Rule enforced: any schema node with {"type": "object"} must include a
    "properties" key (it may be {}).
    """
    from blockscout_mcp_server.server import mcp

    tools = await mcp.list_tools()
    failures: list[str] = []

    for tool in tools:
        tool_dict = tool.model_dump()
        for schema_key in ("inputSchema", "outputSchema"):
            schema = tool_dict.get(schema_key)
            if not isinstance(schema, dict):
                continue

            for node_path, node in _iter_object_schema_nodes(schema, path=f"{tool_dict.get('name')}:{schema_key}"):
                if node.get("type") == "object" and "properties" not in node:
                    failures.append(f"{node_path} is object schema missing properties: {node}")

    assert failures == []


