# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for scripts/slice_impl_plan.py — the plan marker validator/slicer."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "slice_impl_plan.py"
_spec = importlib.util.spec_from_file_location("slice_impl_plan", _MODULE_PATH)
assert _spec and _spec.loader
slicer = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = slicer  # let @dataclass resolve cls.__module__ during exec
_spec.loader.exec_module(slicer)


# A fully valid plan. Note the embedded "## ..." heading inside a fenced block in
# phase-2: it is the whole reason markers exist — a heading-based slicer would
# treat it as a phase boundary, but marker-based slicing keeps it as content.
VALID_PLAN = """\
<!-- impl-plan:begin slug="preamble" -->
# Implementation Plan for Issue #999

**GitHub Issue:** https://example.test/issues/999

## Overview

Do the thing.

## Definition of Done — Test Integrity (non-negotiable)

Tests must genuinely pass.
<!-- impl-plan:end slug="preamble" -->

---

<!-- impl-plan:begin slug="phase-1" title="First phase" -->
## Phase 1: First phase

### Objective

Lay the groundwork.
<!-- impl-plan:end slug="phase-1" -->

<!-- impl-plan:begin slug="phase-2" title="Second `phase`" -->
## Phase 2: Second phase

```markdown
## This embedded heading must NOT create a false boundary
```
<!-- impl-plan:end slug="phase-2" -->

<!-- impl-plan:begin slug="final-checklist" -->
## Final Checklist

- [ ] done
<!-- impl-plan:end slug="final-checklist" -->
"""


def test_valid_plan_validates_clean() -> None:
    regions, errors, markers = slicer.validate_text(VALID_PLAN)
    assert markers is True
    assert errors == []
    assert [r.slug for r in regions] == ["preamble", "phase-1", "phase-2", "final-checklist"]
    assert [r.title for r in regions] == [None, "First phase", "Second `phase`", None]


def test_write_slices_strips_markers_and_preserves_content(tmp_path: Path) -> None:
    regions, errors, _ = slicer.validate_text(VALID_PLAN)
    assert errors == []
    written = slicer.write_slices(regions, tmp_path)

    names = {p.name for p in written}
    assert names == {"preamble.md", "phase-1.md", "phase-2.md", "final-checklist.md"}

    for path in written:
        assert "impl-plan:" not in path.read_text(encoding="utf-8")

    preamble = (tmp_path / "preamble.md").read_text(encoding="utf-8")
    assert "## Definition of Done" in preamble

    phase2 = (tmp_path / "phase-2.md").read_text(encoding="utf-8")
    # The embedded heading survives verbatim inside the phase slice.
    assert "## This embedded heading must NOT create a false boundary" in phase2


def test_write_slices_removes_stale_files(tmp_path: Path) -> None:
    (tmp_path / "phase-9.md").write_text("leftover\n", encoding="utf-8")
    regions, _, _ = slicer.validate_text(VALID_PLAN)
    slicer.write_slices(regions, tmp_path)
    assert not (tmp_path / "phase-9.md").exists()


def test_plain_markdown_has_no_markers() -> None:
    _, errors, markers = slicer.validate_text("# Title\n\n## Phase 1: thing\n")
    assert markers is False
    assert errors == []


def test_missing_end_marker_is_reported() -> None:
    # Drop the last region's end marker: nothing follows to mis-close it, so it
    # surfaces as a genuinely unclosed region.
    broken = VALID_PLAN.replace('<!-- impl-plan:end slug="final-checklist" -->\n', "")
    _, errors, markers = slicer.validate_text(broken)
    assert markers is True
    assert any("never closed" in e for e in errors)


def test_nested_markers_are_reported() -> None:
    nested = VALID_PLAN.replace(
        '<!-- impl-plan:end slug="phase-1" -->',
        '<!-- impl-plan:begin slug="phase-1b" title="oops" -->',
    )
    _, errors, _ = slicer.validate_text(nested)
    assert any("nested markers are not allowed" in e for e in errors)


def test_duplicate_slug_is_reported() -> None:
    dup = VALID_PLAN.replace('slug="phase-2"', 'slug="phase-1"')
    _, errors, _ = slicer.validate_text(dup)
    assert any('"phase-1" appears more than once' in e for e in errors)


def test_orphan_content_outside_regions_is_reported() -> None:
    orphan = VALID_PLAN.replace(
        '<!-- impl-plan:end slug="phase-1" -->\n',
        '<!-- impl-plan:end slug="phase-1" -->\nthis stray sentence escaped its region\n',
    )
    _, errors, _ = slicer.validate_text(orphan)
    assert any("content outside any marked region" in e for e in errors)


def test_non_contiguous_phases_are_reported() -> None:
    gap = VALID_PLAN.replace('slug="phase-2"', 'slug="phase-3"')
    _, errors, _ = slicer.validate_text(gap)
    assert any('expected slug="phase-2"' in e for e in errors)


def test_misplaced_marker_caught_by_content_check() -> None:
    # phase-2 marker now wraps a body that opens with the wrong phase heading.
    bad = VALID_PLAN.replace("## Phase 2: Second phase", "## Phase 5: Wrong phase")
    _, errors, _ = slicer.validate_text(bad)
    assert any('slug="phase-2" does not open with a "## Phase 2" heading' in e for e in errors)


def _write_plan(tmp_path: Path, text: str) -> Path:
    plan = tmp_path / "plan.md"
    plan.write_text(text, encoding="utf-8")
    return plan


def test_cli_inspect_valid_returns_zero_and_writes_nothing(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path, VALID_PLAN)
    out = tmp_path / "out"
    code = slicer.run_cli([str(plan), "--inspect", "--out-dir", str(out)])
    assert code == slicer.EXIT_OK
    assert not out.exists()


def test_cli_slice_valid_writes_files(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path, VALID_PLAN)
    out = tmp_path / "out"
    code = slicer.run_cli([str(plan), "--out-dir", str(out)])
    assert code == slicer.EXIT_OK
    assert (out / "preamble.md").is_file()
    assert (out / "phase-1.md").is_file()
    assert (out / "final-checklist.md").is_file()


def test_cli_no_markers_returns_two(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path, "# Plain plan\n\n## Phase 1: x\n")
    code = slicer.run_cli([str(plan), "--inspect"])
    assert code == slicer.EXIT_NO_MARKERS


def test_cli_malformed_returns_one(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path, VALID_PLAN.replace('<!-- impl-plan:end slug="phase-2" -->\n', ""))
    code = slicer.run_cli([str(plan), "--inspect"])
    assert code == slicer.EXIT_INVALID
