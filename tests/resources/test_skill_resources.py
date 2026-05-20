# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for bundled skill resource enumeration."""

from datetime import datetime
from pathlib import Path

from blockscout_mcp_server.resources import skill_resources

SKILL_ROOT = Path("agent-skills/blockscout-analysis")


def _resource_by_uri(uri: str):
    return {str(resource.uri): resource for resource in skill_resources.list_resources()}[uri]


def _first_non_frontmatter_line(text: str) -> str:
    if not text.startswith("---\n"):
        return text.splitlines()[0]
    body = text.split("\n---\n", 1)[1]
    return body.splitlines()[0]


def test_enumeration_includes_skill_entrypoint():
    assert "blockscout-mcp://skill/SKILL.md" in {str(resource.uri) for resource in skill_resources.list_resources()}


def test_enumeration_includes_all_reference_markdown_files():
    expected = {
        skill_resources.relative_path_to_uri(str(path.relative_to(SKILL_ROOT)))
        for path in (SKILL_ROOT / "references").rglob("*.md")
    }
    actual = {str(resource.uri) for resource in skill_resources.list_resources()}

    assert expected <= actual


def test_enumeration_excludes_root_readme_and_gitignore():
    actual = {str(resource.uri) for resource in skill_resources.list_resources()}

    assert "blockscout-mcp://skill/README.md" not in actual
    assert "blockscout-mcp://skill/.gitignore" not in actual


def test_skill_md_annotations_and_description():
    resource = _resource_by_uri("blockscout-mcp://skill/SKILL.md")

    assert resource.annotations.audience == ["user", "assistant"]
    assert resource.annotations.priority == 0.9
    assert resource.description


def test_reference_annotations_and_no_description():
    resource = _resource_by_uri("blockscout-mcp://skill/references/blockscout-api-index.md")

    assert resource.annotations.audience == ["assistant"]
    assert resource.annotations.priority == 0.2
    assert resource.description is None


def test_last_modified_annotation_is_iso_when_present():
    resource = _resource_by_uri("blockscout-mcp://skill/SKILL.md")
    data = resource.annotations.model_dump()

    if "lastModified" in data:
        datetime.fromisoformat(data["lastModified"])


def test_last_modified_annotation_absent_when_manifest_value_missing(monkeypatch):
    monkeypatch.setattr(skill_resources, "_load_manifest", lambda: {"commit": None, "last_modified": None})

    _, _, resources = skill_resources._build_resources()
    resource = {str(item.uri): item for item in resources}["blockscout-mcp://skill/SKILL.md"]

    assert "lastModified" not in resource.annotations.model_dump()


def test_read_skill_md_strips_frontmatter():
    disk_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    body = skill_resources.read_resource("blockscout-mcp://skill/SKILL.md")

    assert body is not None
    assert not body.startswith("---")
    assert body.startswith(_first_non_frontmatter_line(disk_text))


def test_read_reference_returns_disk_content():
    rel = "references/blockscout-api-index.md"
    body = skill_resources.read_resource(skill_resources.relative_path_to_uri(rel))

    assert body == (SKILL_ROOT / rel).read_text(encoding="utf-8")


def test_read_unknown_uri_returns_none():
    assert skill_resources.read_resource("blockscout-mcp://skill/README.md") is None


def test_read_traversal_shaped_uris_return_none():
    traversal_uris = [
        "blockscout-mcp://skill/../etc/passwd",
        "blockscout-mcp://skill/SKILL.md/../SKILL.md",
        "blockscout-mcp://skill/%2E%2E/etc/passwd",
    ]

    for uri in traversal_uris:
        assert skill_resources.read_resource(uri) is None


def test_missing_skill_entrypoint_raises_runtime_error(monkeypatch, tmp_path):
    package_root = tmp_path / "package"
    package_root.mkdir()
    fake_module = tmp_path / "blockscout_mcp_server" / "resources" / "skill_resources.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("", encoding="utf-8")

    monkeypatch.setattr(skill_resources, "files", lambda _: package_root)
    monkeypatch.setattr(skill_resources, "__file__", str(fake_module))

    try:
        skill_resources._iter_whitelisted_files()
    except RuntimeError as exc:
        assert "Bundled blockscout-analysis skill entrypoint is missing" in str(exc)
    else:
        raise AssertionError("Expected missing skill entrypoint to raise RuntimeError")
