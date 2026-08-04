# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for `SessionStore.check_and_increment`'s explicit `max_calls` ceiling.

This module owns the ceiling-bound scenarios that used to live in
`tests/test_session_store.py` (the `config.session_mcp_max_calls`-monkeypatched
`check_and_increment` tests). Issue #446 turns the ceiling into an explicit
per-call parameter instead of a config read, and adds a zero-ceiling guard
that refuses every identifier — fresh or existing — without creating a row.
Splitting these out keeps `test_session_store.py` under the ~500-LOC
guideline (rule 210 / rule 010 section 6) while giving the new explicit-
parameter and zero-ceiling contract its own focused home.

The tests here construct `SessionStore` instances directly against
`tmp_path` and never touch the module-level singleton, so — unlike the
sibling module — no `_clear_singleton` autouse fixture is needed.
"""

import threading

from blockscout_mcp_server.session_store import SessionStore


def test_check_and_increment_ascends_and_exhausts(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    assert store.check_and_increment("s1", created_at=1_000, max_calls=3) == 1
    assert store.check_and_increment("s1", created_at=1_000, max_calls=3) == 2
    assert store.check_and_increment("s1", created_at=1_000, max_calls=3) == 3
    assert store.check_and_increment("s1", created_at=1_000, max_calls=3) is None

    store.close()


def test_check_and_increment_uses_explicit_bound(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    assert store.check_and_increment("s1", created_at=1_000, max_calls=1) == 1
    assert store.check_and_increment("s1", created_at=1_000, max_calls=1) is None

    store.close()


def test_check_and_increment_zero_ceiling_fresh_identifier_returns_none(tmp_path):
    """A max_calls=0 ceiling refuses even a never-seen identifier and creates no row."""
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    result = store.check_and_increment("never-seen", created_at=1_000, max_calls=0)

    assert result is None
    assert store.get_calls("never-seen") == 0
    store.close()


def test_check_and_increment_concurrent_never_exceeds_max(tmp_path):
    db_path = tmp_path / "sessions.db"
    setup_store = SessionStore(str(db_path))
    setup_store.initialize()
    setup_store.close()

    results: list[int | None] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            worker_store = SessionStore(str(db_path))
            worker_store.initialize()
            result = worker_store.check_and_increment("concurrent-session", created_at=1_000, max_calls=5)
            with lock:
                results.append(result)
            worker_store.close()
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    non_none_results = [r for r in results if r is not None]
    assert len(non_none_results) == 5

    final_store = SessionStore(str(db_path))
    final_store.initialize()
    assert final_store.get_calls("concurrent-session") == 5
    final_store.close()


def test_check_and_increment_mixed_ceilings_concurrent(tmp_path):
    """Cross-surface use (issue #446): concurrent calls with different per-call
    ceilings racing the same identifier must never let the final count exceed
    the higher ceiling, and every result accepted by a lower-ceiling worker
    must itself be <= that lower ceiling.
    """
    db_path = tmp_path / "sessions.db"
    setup_store = SessionStore(str(db_path))
    setup_store.initialize()
    setup_store.close()

    low_ceiling = 3
    high_ceiling = 10
    num_low_workers = 8
    num_high_workers = 20

    results: list[tuple[int, int | None]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(max_calls: int) -> None:
        try:
            worker_store = SessionStore(str(db_path))
            worker_store.initialize()
            result = worker_store.check_and_increment("mixed-session", created_at=1_000, max_calls=max_calls)
            with lock:
                results.append((max_calls, result))
            worker_store.close()
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(low_ceiling,)) for _ in range(num_low_workers)]
    threads += [threading.Thread(target=worker, args=(high_ceiling,)) for _ in range(num_high_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []

    accepted = [result for _, result in results if result is not None]
    assert len(accepted) == len(set(accepted))  # every accepted count is unique

    for max_calls, result in results:
        if max_calls == low_ceiling and result is not None:
            assert result <= low_ceiling

    final_store = SessionStore(str(db_path))
    final_store.initialize()
    assert final_store.get_calls("mixed-session") == high_ceiling
    final_store.close()
