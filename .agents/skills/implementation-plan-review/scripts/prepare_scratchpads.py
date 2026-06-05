#!/usr/bin/env python3
"""Prepare a clean scratchpad directory for implementation-plan-review."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_ERROR = 2


def derive_scratchpad_dir(plan_path: Path) -> Path:
    """Derive the deterministic scratchpad directory for a plan file."""
    if plan_path.name in {"", ".", ".."}:
        msg = f"Unsafe plan filename: {plan_path}"
        raise ValueError(msg)

    scratchpad_name = f"{plan_path.stem}-scratchpads"
    if scratchpad_name in {"", ".", ".."} or not scratchpad_name.endswith("-scratchpads"):
        msg = f"Unsafe scratchpad directory name derived from: {plan_path.name}"
        raise ValueError(msg)

    return plan_path.parent / scratchpad_name


def prepare_scratchpads(plan_path: Path) -> Path:
    """Delete and recreate the scratchpad directory for a plan file."""
    plan_path = plan_path.expanduser()
    plan_parent = plan_path.parent

    if not plan_parent.exists():
        msg = f"Plan parent directory does not exist: {plan_parent}"
        raise ValueError(msg)
    if not plan_parent.is_dir():
        msg = f"Plan parent path is not a directory: {plan_parent}"
        raise ValueError(msg)
    if not plan_path.exists():
        msg = f"Plan file does not exist: {plan_path}"
        raise ValueError(msg)
    if not plan_path.is_file():
        msg = f"Plan path is not a file: {plan_path}"
        raise ValueError(msg)

    scratchpad_dir = derive_scratchpad_dir(plan_path)
    if scratchpad_dir.parent != plan_parent:
        msg = f"Refusing scratchpad path outside the plan directory: {scratchpad_dir}"
        raise ValueError(msg)

    if scratchpad_dir.is_symlink():
        msg = f"Refusing to remove symlink scratchpad path: {scratchpad_dir}"
        raise ValueError(msg)

    if scratchpad_dir.exists():
        if not scratchpad_dir.is_dir():
            msg = f"Scratchpad path exists and is not a directory: {scratchpad_dir}"
            raise ValueError(msg)
        shutil.rmtree(scratchpad_dir)

    scratchpad_dir.mkdir()
    return scratchpad_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete and recreate the deterministic scratchpad directory for an implementation plan."
    )
    parser.add_argument("plan_file", help="Path to the implementation plan file.")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else EXIT_USAGE

    try:
        scratchpad_dir = prepare_scratchpads(Path(args.plan_file))
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(f"OK {scratchpad_dir}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(run_cli())
