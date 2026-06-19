# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for server registration of bundled skill resources."""

from pathlib import Path
from unittest.mock import patch

import pytest

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.resources import skill_resources
from blockscout_mcp_server.server import mcp


@pytest.fixture(autouse=True)
def isolate_sinks(monkeypatch):
    """Close both analytics/telemetry sinks for every test in this module.

    Prevents live network calls to the community endpoint and Mixpanel,
    independent of run order and environment.
    """
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)
    yield
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)


@pytest.mark.asyncio
async def test_server_lists_registered_skill_resources():
    listed = await mcp.list_resources()

    assert len(listed) == len(skill_resources.list_resources())
    assert {str(resource.uri) for resource in listed} == {
        str(resource.uri) for resource in skill_resources.list_resources()
    }


@pytest.mark.asyncio
async def test_server_reads_skill_md_as_text_without_frontmatter():
    contents = await mcp.read_resource("blockscout-mcp://skill/SKILL.md")

    assert isinstance(contents[0].content, str)
    assert not contents[0].content.startswith("---")


@pytest.mark.asyncio
async def test_server_reads_reference_content_from_disk():
    rel = "references/blockscout-api-index.md"
    contents = await mcp.read_resource(skill_resources.relative_path_to_uri(rel))

    assert contents[0].content == (Path("agent-skills/blockscout-analysis") / rel).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_server_read_unknown_resource_raises_not_found():
    with pytest.raises(ValueError, match="Unknown resource"):
        await mcp.read_resource("blockscout-mcp://skill/README.md")


@pytest.mark.asyncio
async def test_successful_read_emits_resource_read_log(caplog):
    """Successful resource read emits an INFO line containing 'Resource read: skill/SKILL.md'."""
    import logging

    with caplog.at_level(logging.INFO, logger="blockscout_mcp_server.observability"):
        await mcp.read_resource("blockscout-mcp://skill/SKILL.md")

    assert any("Resource read: skill/SKILL.md" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_unknown_resource_emits_no_resource_read_log(caplog):
    """Unknown resource read raises and emits no 'Resource read:' log line."""
    import logging

    with caplog.at_level(logging.INFO, logger="blockscout_mcp_server.observability"):
        with pytest.raises(ValueError, match="Unknown resource"):
            await mcp.read_resource("blockscout-mcp://skill/README.md")

    assert not any("Resource read:" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_read_resource_override_calls_helper_with_correct_args(monkeypatch):
    """Override forwards the correct URI and context into the shared observability helper."""
    sentinel_ctx = object()
    monkeypatch.setattr(mcp, "get_context", lambda: sentinel_ctx)

    with patch("blockscout_mcp_server.server.observability.log_resource_read") as mock_helper:
        await mcp.read_resource("blockscout-mcp://skill/SKILL.md")

    mock_helper.assert_called_once()
    call_args = mock_helper.call_args
    assert str(call_args[0][0]) == "blockscout-mcp://skill/SKILL.md"
    assert call_args[0][1] is sentinel_ctx
