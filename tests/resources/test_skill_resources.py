# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for bundled skill resource enumeration."""

import json
from datetime import datetime
from pathlib import Path

import pytest

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

    _, _, resources, _ = skill_resources._build_resources()
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


# ---------------------------------------------------------------------------
# _extract_skill_version — happy path
# ---------------------------------------------------------------------------


def test_extract_skill_version_happy_path():
    frontmatter = {"metadata": '{"author": "blockscout.com", "version": "0.5.0"}'}
    assert skill_resources._extract_skill_version(frontmatter) == "0.5.0"


# ---------------------------------------------------------------------------
# _extract_skill_version — graceful None (never raises)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "frontmatter",
    [
        {},  # "metadata" key absent
        {"metadata": "not json {{{"},  # malformed JSON
        {"metadata": '{"author": "blockscout.com"}'},  # valid JSON, no "version" key
        {"metadata": '{"version": 5}'},  # "version" present but not a string
    ],
    ids=["metadata_absent", "malformed_json", "no_version_key", "version_not_string"],
)
def test_extract_skill_version_returns_none_and_never_raises(frontmatter):
    result = skill_resources._extract_skill_version(frontmatter)
    assert result is None


# ---------------------------------------------------------------------------
# Real bundle — version derived, not hardcoded
# ---------------------------------------------------------------------------


def _version_from_disk() -> str:
    """Parse the version directly from the SKILL.md frontmatter on disk."""
    skill_md_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for line in skill_md_text.splitlines():
        if line.startswith("metadata:"):
            _, _, json_part = line.partition(":")
            return json.loads(json_part.strip())["version"]
    raise AssertionError("metadata: line not found in SKILL.md")


def test_get_bundled_skill_version_matches_disk():
    expected = _version_from_disk()
    assert skill_resources.get_bundled_skill_version() == expected


def test_build_resources_yields_version_from_frontmatter():
    *_, version = skill_resources._build_resources()
    assert version == _version_from_disk()


def test_build_resources_version_none_when_frontmatter_lacks_version(monkeypatch):
    skill_md = '---\nmetadata: {"author": "blockscout.com"}\ndescription: x\n---\nbody\n'
    monkeypatch.setattr(skill_resources, "_iter_whitelisted_files", lambda: [("SKILL.md", skill_md)])

    *_, version = skill_resources._build_resources()

    assert version is None


# ---------------------------------------------------------------------------
# skill_pointer_text — with version
# ---------------------------------------------------------------------------


def test_skill_pointer_text_contains_version():
    version = skill_resources.get_bundled_skill_version()
    text = skill_resources.skill_pointer_text()
    assert f"(version {version})" in text


# ---------------------------------------------------------------------------
# skill_pointer_text — without version (monkeypatched)
# ---------------------------------------------------------------------------


def test_skill_pointer_text_without_version(monkeypatch):
    monkeypatch.setattr(skill_resources, "get_bundled_skill_version", lambda: None)
    text = skill_resources.skill_pointer_text()
    assert "(version" not in text
    assert "{version_note}" not in text
    assert "  " not in text  # no doubled space
