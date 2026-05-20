# SPDX-License-Identifier: LicenseRef-Blockscout
"""Hatch build hook for bundled skill artifacts."""

import json
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Keep these exclusions aligned with agent-skills/tools/package.sh. The .build
# directory is excluded because blockscout-analysis/.gitignore treats it as generated output.
_EXCLUDED_SKILL_ROOT_FILES = {".gitignore", "README.md", ".mcp.json"}
_EXCLUDED_SKILL_DIRS = {".build", ".codex-plugin"}


class BundledSkillMetadataHook(BuildHookInterface):
    """Emit bundled skill content and metadata into the wheel."""

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

        staged_skill_path = Path(self.directory) / "_bundled_skill"
        _stage_bundled_skill(submodule_path, staged_skill_path)

        force_include = build_data.setdefault("force_include", {})
        force_include[str(staged_skill_path)] = "blockscout_mcp_server/_bundled_skill"
        force_include[str(scratch_path)] = "blockscout_mcp_server/_bundled_skill_manifest.json"


def _load_sidecar(path: Path) -> dict[str, str | None] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    commit = data.get("commit")
    last_modified = data.get("last_modified")
    if not isinstance(commit, str) or not commit:
        return None
    if not isinstance(last_modified, str) or not last_modified:
        return None

    return {"commit": commit, "last_modified": last_modified}


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


def _stage_bundled_skill(skill_root: Path, staged_path: Path) -> None:
    if not (skill_root / "SKILL.md").is_file():
        raise RuntimeError(f"Bundled skill entrypoint not found: {skill_root / 'SKILL.md'}")

    if staged_path.exists():
        shutil.rmtree(staged_path)
    staged_path.mkdir(parents=True)

    for source in sorted(skill_root.rglob("*")):
        if not source.is_file() or not _should_bundle_skill_file(skill_root, source):
            continue

        relative_path = source.relative_to(skill_root)
        target = staged_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _should_bundle_skill_file(skill_root: Path, path: Path) -> bool:
    relative_path = path.relative_to(skill_root)
    parts = relative_path.parts
    if any(part in _EXCLUDED_SKILL_DIRS for part in parts):
        return False
    return not (len(parts) == 1 and parts[0] in _EXCLUDED_SKILL_ROOT_FILES)
