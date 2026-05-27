#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Blockscout
"""Run integration tests one-by-one with a per-test wall-clock timeout.

Why this exists
---------------
Integration tests make real network calls to live Blockscout/Chainscout/BENS
endpoints. The HTTP client has no hard request timeout, so a single
unresponsive endpoint can make one test hang for an unbounded amount of time.
When that happens during a plain ``pytest -m integration`` run, the whole suite
(and the agent waiting on it) is blocked indefinitely.

This runner isolates every test in its own subprocess and kills it after
``--timeout`` seconds. A hung test is reported as TIMEOUT and the run continues,
so the agent always gets a bounded, complete report instead of stalling.

It works for the whole suite, a single module/directory, or a single test,
because the positional ``target`` argument is passed straight to pytest's
collector.

Portability notes
-----------------
* No reliance on the ``timeout`` shell command or ``date +%N`` — both are
  missing/broken on macOS. Timing and process control are done in Python.
* ``pytest-timeout`` is intentionally NOT required: it is not part of the
  project's dependencies and its thread method cannot reliably kill a hung
  async network call without taking down the whole pytest process.
* ``uv run pytest`` launches pytest as a grandchild process, so on timeout we
  kill the entire process group (``start_new_session=True`` + ``killpg``),
  otherwise the real pytest worker would survive the kill.
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path


def find_project_root(start: Path) -> Path:
    """Locate the project root by walking up from the script's own location.

    The root is the nearest ancestor that contains a ``tests/integration``
    directory. Resolving it this way (rather than assuming a fixed directory
    depth) keeps the runner portable: it works regardless of where the host
    agent installs this skill on disk.
    """
    for directory in (start, *start.parents):
        if (directory / "tests" / "integration").is_dir():
            return directory
    raise SystemExit(f"Could not locate the project root: no 'tests/integration' directory found in or above {start}.")


PROJECT_ROOT = find_project_root(Path(__file__).resolve().parent)

DEFAULT_TARGET = "tests/integration"
DEFAULT_TIMEOUT = 120
DEFAULT_SLOW = 10.0
DEFAULT_MARKER = "integration"


def detect_runner() -> list[str]:
    """Return the pytest invocation prefix for the current environment.

    Inside the devcontainer (``/.dockerenv`` exists) dependencies are installed
    system-wide, so pytest is called directly. On the host we go through ``uv``.

    This auto-detection covers the two interactive environments only. Other
    environments — notably CI, where ``pip install -e .[test]`` puts the deps
    directly in a bare ``pytest``'s reach and ``uv`` is not installed — should
    pass ``--runner`` explicitly rather than rely on this. Detecting by the mere
    presence of a ``pytest`` binary on PATH is unsafe: on a host a system-wide
    pytest may exist while the project still requires its virtualenv.
    """
    if Path("/.dockerenv").exists():
        return ["pytest"]
    return ["uv", "run", "pytest"]


def collect_tests(runner: list[str], targets: list[str], marker: str) -> list[str]:
    """Return the list of test node ids matching the marker under the targets."""
    cmd = [*runner, "--collect-only", "-q", "-m", marker, "-p", "no:cacheprovider", *targets]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    ids: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("<"):
            ids.append(line)
    if not ids and proc.returncode not in (0, 5):
        # Surface real collection errors (import failures, bad target, etc.).
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
    return ids


def extract_skip_reason(out: str) -> str:
    """Pull the skip reason out of pytest's ``-rs`` short-summary line.

    With ``-rs`` pytest prints ``SKIPPED [1] path:line: <reason>``. The reason is
    the most useful part of an integration skip (network unavailable, missing API
    key, external service down), so we surface it instead of a bare SKIP.
    """
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("SKIPPED"):
            # Split on ": " (colon-space): the path's ":line:" has no space, so
            # the first colon-space is the boundary before the reason text.
            return line.split(": ", 1)[1].strip() if ": " in line else line
    return ""


def run_one(runner: list[str], test_id: str, timeout: int, marker: str) -> tuple[str, float, str]:
    """Run a single test in its own process group; kill it if it overruns.

    Returns ``(status, duration_seconds, detail)`` where status is one of
    PASS / FAIL / SKIP / TIMEOUT. ``detail`` carries the skip reason for SKIP and
    is empty otherwise.
    """
    cmd = [*runner, test_id, "-m", marker, "-q", "-rs", "--no-header", "-p", "no:cacheprovider"]
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        duration = time.monotonic() - start
        if proc.returncode == 0:
            if "skipped" in out and "passed" not in out:
                return "SKIP", duration, extract_skip_reason(out)
            return "PASS", duration, ""
        return "FAIL", duration, ""
    except subprocess.TimeoutExpired:
        # Kill the whole group: uv -> pytest -> (any children).
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        duration = time.monotonic() - start
        return "TIMEOUT", duration, ""


def fmt(status: str, duration: float, test_id: str) -> str:
    return f"{status:<8} {duration:7.1f}s  {test_id}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run integration tests one-by-one with a per-test timeout.",
    )
    parser.add_argument(
        "target",
        nargs="*",
        help=(
            "pytest target(s): a directory, a file (module), or a 'file::test' "
            f"node id. Defaults to '{DEFAULT_TARGET}' (the whole integration suite)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-test wall-clock timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--slow-threshold",
        type=float,
        default=DEFAULT_SLOW,
        help=f"Flag tests slower than this many seconds (default: {DEFAULT_SLOW}).",
    )
    parser.add_argument(
        "--marker",
        default=DEFAULT_MARKER,
        help=f"pytest marker expression to select (default: '{DEFAULT_MARKER}').",
    )
    parser.add_argument(
        "--runner",
        default=None,
        help=(
            "Explicit pytest invocation, overriding auto-detection. Pass this in "
            "environments where the deps are already importable by a bare pytest "
            "and uv is not installed (e.g. CI after `pip install -e .[test]`): "
            "`--runner pytest`. When omitted, the runner is auto-detected "
            "(docker -> pytest, else `uv run pytest`)."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Only list the tests that would run, then exit.",
    )
    args = parser.parse_args()

    targets = args.target or [DEFAULT_TARGET]
    runner = shlex.split(args.runner) if args.runner else detect_runner()

    print(f"Runner: {' '.join(runner)}", flush=True)
    print(f"Target(s): {', '.join(targets)}", flush=True)
    print(f"Per-test timeout: {args.timeout}s\n", flush=True)

    test_ids = collect_tests(runner, targets, args.marker)
    if not test_ids:
        print("No matching tests collected.", flush=True)
        return 0

    if args.list:
        for test_id in test_ids:
            print(test_id, flush=True)
        return 0

    total = len(test_ids)
    results: list[tuple[str, float, str, str]] = []
    for index, test_id in enumerate(test_ids, start=1):
        status, duration, detail = run_one(runner, test_id, args.timeout, args.marker)
        results.append((status, duration, test_id, detail))
        print(f"[{index:>3}/{total}] {fmt(status, duration, test_id)}", flush=True)

    # ---- Summary -----------------------------------------------------------
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "TIMEOUT": 0}
    for status, *_ in results:
        counts[status] = counts.get(status, 0) + 1
    total_time = sum(d for _, d, _, _ in results)

    print("\n" + "=" * 72, flush=True)
    print(
        f"SUMMARY: {counts['PASS']} passed, {counts['FAIL']} failed, "
        f"{counts['SKIP']} skipped, {counts['TIMEOUT']} timed out "
        f"in {total_time:.1f}s",
        flush=True,
    )

    timeouts = [r for r in results if r[0] == "TIMEOUT"]
    if timeouts:
        print(f"\nTIMED OUT (>{args.timeout}s) — investigate / optimize these:", flush=True)
        for status, duration, test_id, _ in timeouts:
            print(f"  {fmt(status, duration, test_id)}", flush=True)

    failures = [r for r in results if r[0] == "FAIL"]
    if failures:
        print("\nFAILED:", flush=True)
        for status, duration, test_id, _ in failures:
            print(f"  {fmt(status, duration, test_id)}", flush=True)

    skipped = [r for r in results if r[0] == "SKIP"]
    if skipped:
        # Skips are expected for integration tests (offline, missing key, service
        # down), so surface the reason — it's the whole point of inspecting them.
        print("\nSKIPPED (reason):", flush=True)
        for status, duration, test_id, detail in skipped:
            print(f"  {test_id}: {detail or '(no reason reported)'}", flush=True)

    slow = sorted(
        (r for r in results if r[0] != "TIMEOUT" and r[1] >= args.slow_threshold),
        key=lambda r: r[1],
        reverse=True,
    )
    if slow:
        print(f"\nSLOW (>={args.slow_threshold:g}s, completed):", flush=True)
        for status, duration, test_id, _ in slow:
            print(f"  {fmt(status, duration, test_id)}", flush=True)

    return 1 if (failures or timeouts) else 0


if __name__ == "__main__":
    sys.exit(main())
