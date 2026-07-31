# SPDX-License-Identifier: LicenseRef-Blockscout
"""Durable per-session call counter backed by a synchronous SQLite database.

The session-gated free tier (see the module's design notes in the Issue #442
implementation plan) needs a small, atomic check-and-increment counter keyed by
``session_id`` that survives process restarts, because the configured TTL can
span days. SQLite in WAL mode with ``synchronous=NORMAL`` gives durability
across clean restarts at microsecond cost for a single-row upsert, which is why
this module talks to ``sqlite3`` directly on the event loop rather than through
a thread pool or ``aiosqlite``: the hot path is one primary-key upsert against
a single production connection, and offloading it would add latency without
buying anything. This is a deliberate, settled design choice — do not change it
without revisiting the design discussion referenced by the implementation plan.

The database also stores a random "store generation" value alongside the
counters. Phase 3 (session tokens) mixes the generation into every issued
token's MAC, so replacing or losing the database file invalidates every
previously issued identifier instead of silently restoring their budgets.
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path

from blockscout_mcp_server.config import config

_MIN_SQLITE_VERSION = (3, 37, 0)
_MIN_SQLITE_VERSION_STR = "3.37.0"

# PRAGMA busy_timeout, in milliseconds. The single production connection never
# contends with itself, so this never fires in normal operation; it exists for
# the multi-connection concurrency test and as a hard cap on how long a store
# call could stall the event loop if an external process ever held the file's
# write lock (out of contract — see the module docstring/plan).
_BUSY_TIMEOUT_MS = 5_000

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    calls INTEGER NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions (created_at);

CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY CHECK (id = 0),
    generation TEXT NOT NULL
) STRICT;
"""


class SessionStoreInitializationError(Exception):
    """Raised when the session store cannot be initialized (fail-fast)."""


class SessionStore:
    """Synchronous SQLite-backed counter store for session-gated tool calls."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._generation: str = ""

    @property
    def generation(self) -> str:
        """Return the store's generation, established at initialization time."""
        return self._generation

    def initialize(self) -> None:
        """Open (creating if needed) the database and prepare it for use.

        Raises:
            SessionStoreInitializationError: if the SQLite version is too old,
                the parent directory does not exist, or the database cannot be
                opened/written to.
        """
        if sqlite3.sqlite_version_info < _MIN_SQLITE_VERSION:
            raise SessionStoreInitializationError(
                f"Session store requires SQLite >= {_MIN_SQLITE_VERSION_STR}, found {sqlite3.sqlite_version}."
            )

        parent = Path(self._path).parent
        if not parent.is_dir():
            raise SessionStoreInitializationError(
                f"Session store directory does not exist: {parent}. Refusing to create it "
                "automatically — mount the expected volume or point BLOCKSCOUT_SESSION_DB_PATH "
                "at an existing directory."
            )

        try:
            conn = sqlite3.connect(self._path, isolation_level=None, check_same_thread=True)
            conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(_DDL)
            # Probe writability with a real write (rewriting the current
            # user_version — a header write even when the value is unchanged;
            # the schema never uses user_version). On a database that already
            # carries the schema every statement above is a no-op read, and
            # SQLite silently opens an unwritable file read-only, so without
            # this probe an ro-remounted volume would pass initialization and
            # fail only at runtime, on the first debit.
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            conn.execute(f"PRAGMA user_version = {user_version}")
        except sqlite3.Error as exc:
            raise SessionStoreInitializationError(f"Failed to initialize session store at {self._path}: {exc}") from exc

        self._conn = conn
        self._generation = self._load_or_create_generation()

    def _load_or_create_generation(self) -> str:
        assert self._conn is not None
        row = self._conn.execute("SELECT generation FROM meta WHERE id = 0").fetchone()
        if row is not None:
            return row[0]
        generation = secrets.token_hex(16)
        self._conn.execute(
            "INSERT INTO meta (id, generation) VALUES (0, :generation)",
            {"generation": generation},
        )
        return generation

    def check_and_increment(self, session_id: str, created_at: int) -> int | None:
        """Atomically increment the call counter for ``session_id``.

        Returns the new call count, or ``None`` if the budget (``config.session_max_calls``)
        is already exhausted. Creates the row (with ``calls = 1``) on first use.
        """
        assert self._conn is not None
        max_calls = config.session_max_calls
        rows = self._conn.execute(
            """
            INSERT INTO sessions (id, created_at, calls)
            VALUES (:id, :created_at, 1)
            ON CONFLICT(id) DO UPDATE SET calls = calls + 1
            WHERE calls < :max_calls
            RETURNING calls
            """,
            {"id": session_id, "created_at": created_at, "max_calls": max_calls},
        ).fetchall()
        if not rows:
            return None
        return rows[0][0]

    def refund(self, session_id: str) -> None:
        """Decrement the call counter for ``session_id`` by one.

        A no-op when the row is missing or already at zero — never goes negative.
        """
        assert self._conn is not None
        self._conn.execute(
            "UPDATE sessions SET calls = calls - 1 WHERE id = :id AND calls > 0",
            {"id": session_id},
        )

    def get_calls(self, session_id: str) -> int:
        """Return the current call count for ``session_id`` without creating a row."""
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT calls FROM sessions WHERE id = :id",
            {"id": session_id},
        ).fetchone()
        return row[0] if row is not None else 0

    def sweep_batch(self, limit: int, now: float | None = None) -> int:
        """Delete up to ``limit`` expired rows and return how many were deleted.

        Expiry is determined by ``config.session_ttl_seconds`` at call time, the
        same value the token-verification path (Phase 3) uses, so a swept row's
        token would already be rejected as expired.
        """
        assert self._conn is not None
        current_time = time.time() if now is None else now
        cutoff = current_time - config.session_ttl_seconds
        rows = self._conn.execute(
            """
            DELETE FROM sessions
            WHERE rowid IN (
                SELECT rowid FROM sessions WHERE created_at < :cutoff LIMIT :limit
            )
            RETURNING rowid
            """,
            {"cutoff": cutoff, "limit": limit},
        ).fetchall()
        return len(rows)

    def close(self) -> None:
        """Close the underlying connection. Idempotent."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


_store: SessionStore | None = None


def initialize_store(path: str) -> SessionStore:
    """Create, initialize, and register the module-level session store singleton."""
    global _store
    store = SessionStore(path)
    store.initialize()
    _store = store
    return store


def get_store() -> SessionStore:
    """Return the initialized module-level session store singleton.

    Raises:
        RuntimeError: if the store was never initialized via ``initialize_store``.
    """
    if _store is None:
        raise RuntimeError("Session store has not been initialized. Call initialize_store() first.")
    return _store


def close_store() -> None:
    """Close and clear the module-level session store singleton.

    A silent no-op when the store was never initialized (or already closed),
    since the HTTP shutdown path calls this unconditionally regardless of
    whether session gating was ever enabled.
    """
    global _store
    if _store is None:
        return
    _store.close()
    _store = None
