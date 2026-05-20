# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for custom Hatch build hook helpers."""

import importlib
import sys
import types

import pytest


def _import_hatch_build(monkeypatch):
    interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")

    class BuildHookInterface:
        pass

    interface.BuildHookInterface = BuildHookInterface

    module_names = [
        "hatchling",
        "hatchling.builders",
        "hatchling.builders.hooks",
        "hatchling.builders.hooks.plugin",
    ]
    for name in module_names:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "hatchling.builders.hooks.plugin.interface", interface)
    sys.modules.pop("hatch_build", None)
    return importlib.import_module("hatch_build")


def test_stage_bundled_skill_matches_skill_package_exclusions(monkeypatch, tmp_path):
    hatch_build = _import_hatch_build(monkeypatch)
    skill_root = tmp_path / "blockscout-analysis"
    staged_path = tmp_path / "staged"

    included_files = [
        "SKILL.md",
        "references/blockscout-api-index.md",
        "references/blockscout-api/addresses.md",
    ]
    excluded_files = [
        ".gitignore",
        "README.md",
        ".mcp.json",
        ".build/generated.md",
        ".codex-plugin/plugin.json",
    ]

    for rel in included_files + excluded_files:
        path = skill_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rel, encoding="utf-8")

    hatch_build._stage_bundled_skill(skill_root, staged_path)

    for rel in included_files:
        assert (staged_path / rel).read_text(encoding="utf-8") == rel
    for rel in excluded_files:
        assert not (staged_path / rel).exists()


def test_stage_bundled_skill_rejects_symlinks(monkeypatch, tmp_path):
    hatch_build = _import_hatch_build(monkeypatch)
    skill_root = tmp_path / "blockscout-analysis"
    staged_path = tmp_path / "staged"
    external_file = tmp_path / "external.md"
    symlink_path = skill_root / "references" / "external.md"

    (skill_root / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text("skill", encoding="utf-8")
    symlink_path.parent.mkdir(parents=True, exist_ok=True)
    external_file.write_text("outside skill root", encoding="utf-8")
    symlink_path.symlink_to(external_file)

    with pytest.raises(RuntimeError) as exc_info:
        hatch_build._stage_bundled_skill(skill_root, staged_path)

    assert "Bundled skill staging refuses symlink" in str(exc_info.value)
    assert str(symlink_path) in str(exc_info.value)
