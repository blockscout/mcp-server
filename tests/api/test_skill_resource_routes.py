# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the bundled skill HTTP mirror."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server import analytics
from blockscout_mcp_server.api import routes
from blockscout_mcp_server.api.routes import register_api_routes
from blockscout_mcp_server.config import config

SKILL_ROOT = Path("agent-skills/blockscout-analysis")


@pytest.fixture(autouse=True)
def isolate_sinks(monkeypatch):
    """Prevent live network calls to analytics and community-telemetry sinks.

    The real log_resource_read fans out to two sinks that may make HTTP calls:
    1. analytics.track_resource_read — fires when analytics HTTP mode is on and
       mixpanel_token is set.
    2. telemetry.send_community_resource_report — scheduled via asyncio.create_task;
       makes an HTTP POST to the community endpoint unless
       config.disable_community_telemetry is True.

    This fixture closes both deterministically, independent of run order.
    """
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)
    yield
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)


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


# ---------------------------------------------------------------------------
# Observability tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_md_success_emits_log(client: AsyncClient, caplog):
    """A 200 response emits an INFO log line containing 'Resource read: skill/SKILL.md'."""
    import logging

    with caplog.at_level(logging.INFO, logger="blockscout_mcp_server.observability"):
        response = await client.get("/skill/SKILL.md")

    assert response.status_code == 200
    assert any("Resource read: skill/SKILL.md" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_skill_md_success_transport_attribution(client: AsyncClient):
    """A 200 response calls log_resource_read with the canonical full URI and a REST context."""
    with patch.object(routes.observability, "log_resource_read", new_callable=MagicMock) as mock_log:
        response = await client.get("/skill/SKILL.md")

    assert response.status_code == 200
    mock_log.assert_called_once()
    call_args = mock_log.call_args

    # First arg: canonical full URI string
    assert call_args[0][0] == "blockscout-mcp://skill/SKILL.md"

    # Second arg: context with call_source="rest" and a live Starlette request
    ctx = call_args[0][1]
    assert ctx.call_source == "rest"
    assert ctx.request_context is not None
    assert ctx.request_context.request is not None


@pytest.mark.asyncio
async def test_404_path_emits_no_log(client: AsyncClient, caplog):
    """A 404 response does not emit any 'Resource read:' log line."""
    import logging

    with caplog.at_level(logging.INFO, logger="blockscout_mcp_server.observability"):
        response = await client.get("/skill/README.md")

    assert response.status_code == 404
    assert not any("Resource read:" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_404_path_does_not_call_log_resource_read(client: AsyncClient):
    """A 404 response does not call observability.log_resource_read at all."""
    with patch.object(routes.observability, "log_resource_read", new_callable=MagicMock) as mock_log:
        response = await client.get("/skill/does/not/exist.md")

    assert response.status_code == 404
    mock_log.assert_not_called()
