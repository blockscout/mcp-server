#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Blockscout
"""Bake blockscout-analysis submodule commit metadata into a root sidecar."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMODULE_PATH = ROOT / "agent-skills" / "blockscout-analysis"
SIDECAR_PATH = ROOT / ".bundle_skill_commit_info.json"


def main() -> None:
    result = subprocess.run(
        ["git", "-C", str(SUBMODULE_PATH), "log", "-1", "--format=%H%n%cI"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    if len(lines) < 2:
        raise RuntimeError("Could not read blockscout-analysis commit hash and timestamp")

    data = {"commit": lines[0], "last_modified": lines[1]}
    SIDECAR_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
