# SPDX-License-Identifier: LicenseRef-Blockscout
"""Hatch build hook for bundled skill metadata."""

import json
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class BundledSkillMetadataHook(BuildHookInterface):
    """Emit bundled skill metadata into the wheel."""

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        sidecar_path = root / ".bundle_skill_commit_info.json"
        submodule_path = root / "agent-skills" / "blockscout-analysis"

        metadata = _load_sidecar(sidecar_path)
        if metadata is None:
            metadata = _load_git_metadata(submodule_path)
        if metadata is None:
            metadata = {"commit": None, "last_modified": None}

        scratch_path = Path(self.directory) / "_bundled_skill_manifest.json"
        scratch_path.parent.mkdir(parents=True, exist_ok=True)
        scratch_path.write_text(json.dumps(metadata, separators=(",", ":")), encoding="utf-8")

        force_include = build_data.setdefault("force_include", {})
        force_include[str(scratch_path)] = "blockscout_mcp_server/_bundled_skill_manifest.json"


def _load_sidecar(path: Path) -> dict[str, str | None] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return {
        "commit": data.get("commit"),
        "last_modified": data.get("last_modified"),
    }


def _load_git_metadata(submodule_path: Path) -> dict[str, str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(submodule_path), "log", "-1", "--format=%H%n%cI"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    lines = result.stdout.splitlines()
    if len(lines) < 2 or not lines[0] or not lines[1]:
        return None

    return {"commit": lines[0], "last_modified": lines[1]}
