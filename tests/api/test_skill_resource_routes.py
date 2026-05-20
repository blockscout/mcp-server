# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the bundled skill HTTP mirror."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.api.routes import register_api_routes

SKILL_ROOT = Path("agent-skills/blockscout-analysis")


@pytest.fixture
def test_mcp_instance():
    return FastMCP(name="test-skill-resource-routes")


@pytest.fixture
def client(test_mcp_instance):
    register_api_routes(test_mcp_instance)
    asgi_app = test_mcp_instance.streamable_http_app()
    return AsyncClient(transport=ASGITransport(app=asgi_app), base_url="http://test")


def _first_non_frontmatter_line(text: str) -> str:
    if not text.startswith("---\n"):
        return text.splitlines()[0]
    body = text.split("\n---\n", 1)[1]
    return body.splitlines()[0]


@pytest.mark.asyncio
async def test_skill_md_success(client: AsyncClient):
    disk_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    response = await client.get("/skill/SKILL.md")

    assert response.status_code == 200
    assert response.text.startswith(_first_non_frontmatter_line(disk_text))
    assert "text/markdown" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_reference_success(client: AsyncClient):
    rel = "references/blockscout-api-index.md"

    response = await client.get(f"/skill/{rel}")

    assert response.status_code == 200
    assert response.text == (SKILL_ROOT / rel).read_text(encoding="utf-8")
    assert "text/markdown" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_readme_not_found(client: AsyncClient):
    response = await client.get("/skill/README.md")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unknown_path_not_found(client: AsyncClient):
    response = await client.get("/skill/does/not/exist.md")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_traversal_returns_404(client: AsyncClient):
    response = await client.get("/skill/../etc/passwd")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_encoded_traversal_returns_404(client: AsyncClient):
    response = await client.get("/skill/%2E%2E/etc/passwd")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_route_not_registered_before_register_api_routes():
    test_mcp = FastMCP(name="test-clean-skill-route")
    async with AsyncClient(
        transport=ASGITransport(app=test_mcp.streamable_http_app()),
        base_url="http://test",
    ) as test_client:
        response = await test_client.get("/skill/SKILL.md")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_skill_returns_404(client: AsyncClient):
    response = await client.get("/v1/skill/SKILL.md")

    assert response.status_code == 404
