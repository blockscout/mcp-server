# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for bundled blockscout-analysis skill artifact availability."""

import json
import re
import subprocess
from datetime import datetime
from importlib.resources import files
from pathlib import Path


def test_skill_entrypoint_available_from_package_or_source_tree():
    """The skill entrypoint is available to local tests and package builds."""
    package_skill = files("blockscout_mcp_server") / "_bundled_skill" / "SKILL.md"
    source_skill = Path("agent-skills/blockscout-analysis/SKILL.md")
    skill_path = package_skill if package_skill.is_file() else source_skill

    assert skill_path.is_file()
    assert "# Blockscout Analysis" in skill_path.read_text(encoding="utf-8")


def test_known_reference_file_available_from_package_or_source_tree():
    """A known reference file is present and non-empty."""
    package_ref = files("blockscout_mcp_server") / "_bundled_skill" / "references" / "blockscout-api-index.md"
    source_ref = Path("agent-skills/blockscout-analysis/references/blockscout-api-index.md")
    ref_path = package_ref if package_ref.is_file() else source_ref

    assert ref_path.is_file()
    assert ref_path.read_text(encoding="utf-8").strip()


def test_bundled_skill_manifest_shape():
    """The manifest has the expected shape when package or baked sidecar metadata exists."""
    package_manifest = files("blockscout_mcp_server") / "_bundled_skill_manifest.json"
    source_sidecar = Path(".bundle_skill_commit_info.json")
    if package_manifest.is_file():
        manifest = json.loads(package_manifest.read_text(encoding="utf-8"))
    elif source_sidecar.is_file():
        manifest = json.loads(source_sidecar.read_text(encoding="utf-8"))
    else:
        result = subprocess.run(
            ["git", "-C", "agent-skills/blockscout-analysis", "log", "-1", "--format=%H%n%cI"],
            check=False,
            capture_output=True,
            text=True,
        )
        lines = result.stdout.splitlines()
        manifest = (
            {"commit": lines[0], "last_modified": lines[1]}
            if result.returncode == 0 and len(lines) >= 2
            else {"commit": None, "last_modified": None}
        )

    assert set(manifest.keys()) == {"commit", "last_modified"}

    if manifest["commit"] is not None:
        assert re.fullmatch(r"[0-9a-f]{40}", manifest["commit"])
    if manifest["last_modified"] is not None:
        datetime.fromisoformat(manifest["last_modified"])
