# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for server registration of bundled skill resources."""

from pathlib import Path

import pytest

from blockscout_mcp_server.resources import skill_resources
from blockscout_mcp_server.server import mcp


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
