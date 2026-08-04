# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the SQLite-backed session call-counter store."""

import sqlite3
import stat
import time

import pytest

from blockscout_mcp_server import session_store
from blockscout_mcp_server.config import config
from blockscout_mcp_server.session_store import (
    SessionStore,
    SessionStoreInitializationError,
    close_store,
    get_store,
    initialize_store,
)


@pytest.fixture(autouse=True)
def _clear_singleton():
    """Ensure the module-level singleton never leaks between tests."""
    close_store()
    yield
    close_store()


def test_initialize_creates_database_and_table(tmp_path):
    db_path = tmp_path / "sessions.db"
    store = SessionStore(str(db_path))

    store.initialize()

    assert db_path.exists()
    conn = sqlite3.connect(str(db_path))
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    store.close()

    assert "sessions" in tables
    assert "meta" in tables


def test_initialize_missing_parent_directory_raises(tmp_path):
    db_path = tmp_path / "does" / "not" / "exist" / "sessions.db"
    store = SessionStore(str(db_path))

    with pytest.raises(SessionStoreInitializationError, match=str(db_path.parent)):
        store.initialize()

    assert not db_path.parent.exists()
    assert not db_path.exists()


def test_initialize_sqlite_version_preflight(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 36, 0))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.36.0")
    store = SessionStore(str(db_path))

    with pytest.raises(SessionStoreInitializationError, match="3.36.0") as exc_info:
        store.initialize()

    assert "3.37.0" in str(exc_info.value)
    assert not db_path.exists()


def test_initialize_unwritable_path_raises(tmp_path):
    # Point the "database file" at a directory-as-file: sqlite3 cannot open it.
    directory_as_file = tmp_path / "not_a_file"
    directory_as_file.mkdir()
    store = SessionStore(str(directory_as_file))

    with pytest.raises(SessionStoreInitializationError):
        store.initialize()


def test_initialize_readonly_directory_raises(tmp_path):
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    db_path = readonly_dir / "sessions.db"
    store = SessionStore(str(db_path))

    try:
        with pytest.raises(SessionStoreInitializationError):
            store.initialize()
    finally:
        readonly_dir.chmod(stat.S_IRWXU)


def test_initialize_readonly_existing_db_raises(tmp_path):
    # A database that already carries the full schema performs no writes during
    # ordinary initialization, and SQLite silently opens an unwritable file
    # read-only — so without the explicit write probe an ro-remounted volume
    # would pass startup ("ENABLED") and every debit would fail at runtime.
    db_path = tmp_path / "sessions.db"
    store = SessionStore(str(db_path))
    store.initialize()
    store.close()

    artifacts = [db_path, tmp_path / "sessions.db-wal", tmp_path / "sessions.db-shm"]
    for artifact in artifacts:
        if artifact.exists():
            artifact.chmod(stat.S_IRUSR)

    reopened = SessionStore(str(db_path))
    try:
        with pytest.raises(SessionStoreInitializationError):
            reopened.initialize()
    finally:
        for artifact in artifacts:
            if artifact.exists():
                artifact.chmod(stat.S_IRWXU)


def test_store_generation_persists_across_reopen(tmp_path):
    db_path = tmp_path / "sessions.db"
    store = SessionStore(str(db_path))
    store.initialize()
    generation = store.generation
    assert generation
    store.close()

    reopened = SessionStore(str(db_path))
    reopened.initialize()
    assert reopened.generation == generation
    reopened.close()


def test_store_generation_differs_for_fresh_database(tmp_path):
    db_path = tmp_path / "sessions.db"
    store = SessionStore(str(db_path))
    store.initialize()
    generation = store.generation
    store.close()

    db_path.unlink()

    fresh_store = SessionStore(str(db_path))
    fresh_store.initialize()
    assert fresh_store.generation != generation
    fresh_store.close()


def test_durability_across_reopen(tmp_path):
    db_path = tmp_path / "sessions.db"
    store = SessionStore(str(db_path))
    store.initialize()

    store.check_and_increment("session-a", created_at=1_000, max_calls=5)
    store.check_and_increment("session-a", created_at=1_000, max_calls=5)
    store.check_and_increment("session-a", created_at=1_000, max_calls=5)
    store.refund("session-a")
    store.close()

    reopened = SessionStore(str(db_path))
    reopened.initialize()
    assert reopened.get_calls("session-a") == 2
    reopened.close()


def test_refund_decrements(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    store.check_and_increment("s1", created_at=1_000, max_calls=5)
    store.check_and_increment("s1", created_at=1_000, max_calls=5)
    store.refund("s1")

    assert store.get_calls("s1") == 1
    store.close()


def test_refund_missing_id_is_noop(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    store.refund("unknown-session")

    assert store.get_calls("unknown-session") == 0
    store.close()


def test_refund_at_zero_is_noop(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    store.check_and_increment("s1", created_at=1_000, max_calls=5)
    store.refund("s1")
    store.refund("s1")

    assert store.get_calls("s1") == 0
    store.close()


def test_increment_refund_increment_sequence(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    assert store.check_and_increment("s1", created_at=1_000, max_calls=2) == 1
    assert store.check_and_increment("s1", created_at=1_000, max_calls=2) == 2
    assert store.check_and_increment("s1", created_at=1_000, max_calls=2) is None
    store.refund("s1")
    assert store.check_and_increment("s1", created_at=1_000, max_calls=2) == 2
    assert store.check_and_increment("s1", created_at=1_000, max_calls=2) is None

    store.close()


def test_sweep_deletes_expired_and_keeps_fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    now = 1_000_000
    store.check_and_increment("old-session", created_at=now - 200, max_calls=100)
    store.check_and_increment("fresh-session", created_at=now - 10, max_calls=100)

    deleted = store.sweep_batch(limit=1_000, now=now)

    assert deleted == 1
    assert store.get_calls("old-session") == 0
    assert store.get_calls("fresh-session") == 1
    store.close()


def test_sweep_on_empty_table_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    assert store.sweep_batch(limit=1_000, now=1_000_000) == 0
    store.close()


def test_sweep_batch_bound_drains_backlog(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    now = 1_000_000
    for i in range(7):
        store.check_and_increment(f"old-{i}", created_at=now - 200, max_calls=100)
    store.check_and_increment("fresh-session", created_at=now - 10, max_calls=100)

    first = store.sweep_batch(limit=3, now=now)
    assert first == 3

    second = store.sweep_batch(limit=3, now=now)
    assert second == 3

    third = store.sweep_batch(limit=3, now=now)
    assert third == 1

    fourth = store.sweep_batch(limit=3, now=now)
    assert fourth == 0

    assert store.get_calls("fresh-session") == 1
    store.close()


def test_sweep_only_deletes_rows_older_than_ttl_cutoff(tmp_path, monkeypatch):
    ttl = 300
    monkeypatch.setattr(config, "session_ttl_seconds", ttl)
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    now = 2_000_000
    cutoff = now - ttl
    store.check_and_increment("just-expired", created_at=cutoff - 1, max_calls=100)
    store.check_and_increment("just-alive", created_at=cutoff + 1, max_calls=100)

    deleted = store.sweep_batch(limit=1_000, now=now)

    assert deleted == 1
    assert store.get_calls("just-expired") == 0
    assert store.get_calls("just-alive") == 1
    store.close()


def test_get_calls_unknown_id_creates_no_row(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    assert store.get_calls("never-seen") == 0

    conn = sqlite3.connect(str(tmp_path / "sessions.db"))
    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    conn.close()
    store.close()

    assert count == 0


def test_get_calls_known_id_returns_count(tmp_path):
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()

    store.check_and_increment("s1", created_at=1_000, max_calls=5)
    store.check_and_increment("s1", created_at=1_000, max_calls=5)

    assert store.get_calls("s1") == 2
    store.close()


def test_close_store_without_initialize_is_noop():
    close_store()
    close_store()


def test_close_store_idempotent_after_initialize(tmp_path):
    initialize_store(str(tmp_path / "sessions.db"))
    close_store()
    close_store()


def test_initialize_store_after_close_store_succeeds(tmp_path):
    db_path = tmp_path / "sessions.db"
    initialize_store(str(db_path))
    close_store()

    store = initialize_store(str(db_path))
    assert store is get_store()
    close_store()


def test_initialize_store_closes_previous_singleton(tmp_path):
    first = initialize_store(str(tmp_path / "first.db"))

    second = initialize_store(str(tmp_path / "second.db"))

    assert first._conn is None  # closed, not leaked
    assert get_store() is second


def test_failed_reinitialize_leaves_previous_singleton_usable(tmp_path):
    first = initialize_store(str(tmp_path / "first.db"))

    with pytest.raises(SessionStoreInitializationError):
        initialize_store(str(tmp_path / "does" / "not" / "exist" / "second.db"))

    assert get_store() is first
    assert first.get_calls("some-id") == 0  # the connection still works


def test_initialize_setup_failure_closes_connection(tmp_path, monkeypatch):
    # Garbage bytes make the first page read fail after sqlite3.connect() has
    # already succeeded (SQLite opens lazily), exercising the setup-phase
    # error path, which must close the just-opened connection.
    db_path = tmp_path / "sessions.db"
    db_path.write_bytes(b"this is definitely not a sqlite database file")

    captured: dict[str, sqlite3.Connection] = {}
    real_connect = sqlite3.connect

    def capturing_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        captured["conn"] = conn
        return conn

    monkeypatch.setattr(session_store.sqlite3, "connect", capturing_connect)

    store = SessionStore(str(db_path))
    with pytest.raises(SessionStoreInitializationError):
        store.initialize()

    with pytest.raises(sqlite3.ProgrammingError):
        captured["conn"].execute("SELECT 1")


def test_initialize_wraps_generation_load_failure_and_closes_connection(tmp_path, monkeypatch):
    # A pre-existing `meta` table without the `generation` column survives the
    # CREATE TABLE IF NOT EXISTS in the DDL, so the failure surfaces only when
    # the generation is loaded — that error must be wrapped in
    # SessionStoreInitializationError (not escape as a raw sqlite3 error) and
    # must close the connection.
    db_path = tmp_path / "sessions.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE meta (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    captured: dict[str, sqlite3.Connection] = {}
    real_connect = sqlite3.connect

    def capturing_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        captured["conn"] = connection
        return connection

    monkeypatch.setattr(session_store.sqlite3, "connect", capturing_connect)

    store = SessionStore(str(db_path))
    with pytest.raises(SessionStoreInitializationError, match="generation"):
        store.initialize()

    with pytest.raises(sqlite3.ProgrammingError):
        captured["conn"].execute("SELECT 1")


def test_get_store_raises_when_uninitialized():
    with pytest.raises(RuntimeError):
        get_store()


def test_time_module_uses_wall_clock_not_monotonic(tmp_path, monkeypatch):
    """Sanity check that sweep_batch's default clock is time.time(), not monotonic."""
    called = {}
    real_time = time.time

    def fake_time():
        called["used"] = True
        return real_time()

    monkeypatch.setattr(session_store.time, "time", fake_time)
    store = SessionStore(str(tmp_path / "sessions.db"))
    store.initialize()
    store.sweep_batch(limit=10)

    assert called.get("used") is True
    store.close()
