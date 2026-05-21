# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for resource discovery REST API routes."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import FunctionResource
from mcp.types import Annotations, Resource
from pydantic import AnyUrl


@pytest.mark.asyncio
async def test_list_resources_success(client: AsyncClient, test_mcp_instance: FastMCP):
    """Verify that the /v1/resources endpoint returns a list of resources."""
    test_mcp_instance.list_resources = AsyncMock(return_value=[])
    response = await client.get("/v1/resources")
    assert response.status_code == 200
    assert response.json() == []
    test_mcp_instance.list_resources.assert_called_once()


@pytest.mark.asyncio
async def test_list_resources_with_items(client: AsyncClient, test_mcp_instance: FastMCP):
    """Verify resources are serialized with protocol aliases and JSON-safe URLs."""
    resource = Resource(
        uri=AnyUrl("blockscout-mcp://skill/SKILL.md"),
        name="Blockscout Analysis Skill",
        description="Bundled skill root file",
        mimeType="text/markdown",
        annotations=Annotations(audience=["assistant"], priority=0.9),
        _meta={"source": "test"},
    )

    test_mcp_instance.list_resources = AsyncMock(return_value=[resource])

    response = await client.get("/v1/resources")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["uri"] == "blockscout-mcp://skill/SKILL.md"
    assert payload[0]["mimeType"] == "text/markdown"
    assert payload[0]["annotations"]["audience"] == ["assistant"]
    assert payload[0]["annotations"]["priority"] == 0.9
    assert payload[0]["_meta"] == {"source": "test"}
    assert "meta" not in payload[0]

    test_mcp_instance.list_resources.assert_called_once()


@pytest.mark.asyncio
async def test_list_resources_with_real_registration(client: AsyncClient, test_mcp_instance: FastMCP):
    """Verify /v1/resources returns data for an actually registered resource."""

    def _resource_body() -> str:
        return "hello"

    test_mcp_instance.add_resource(
        FunctionResource(
            uri=AnyUrl("blockscout-mcp://skill/TEST.md"),
            name="TEST.md",
            description="Test resource",
            mime_type="text/markdown",
            annotations=Annotations(audience=["assistant"], priority=0.2),
            fn=_resource_body,
        )
    )

    response = await client.get("/v1/resources")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["uri"] == "blockscout-mcp://skill/TEST.md"
    assert payload[0]["name"] == "TEST.md"
    assert payload[0]["mimeType"] == "text/markdown"
