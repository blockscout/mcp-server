# SPDX-License-Identifier: LicenseRef-Blockscout
"""Server lifecycle wiring for the session-gated free tier (issue #442).

This module is the composed lifespan owner for the HTTP ASGI app: it validates
gated-startup preconditions, initializes/closes the session store, emits the
startup status lines, and runs the periodic expiry sweep. It also carries the
relocated ``WEB3_POOL`` shutdown closure — this module is the one place that
owns "what happens across the whole HTTP app's lifetime", not only the session
pieces, because ``mcp.streamable_http_app()`` builds its Starlette app with a
custom ``lifespan`` callable (``lambda app: self.session_manager.run()`` in
the pinned ``mcp`` 1.26). When a Starlette router has a custom lifespan, its
``on_startup``/``on_shutdown`` handler lists (the ones ``add_event_handler``
appends to) are never invoked — silently. That is why the previous
``asgi_app.add_event_handler("shutdown", WEB3_POOL.close)`` in ``server.py``
never actually ran in HTTP mode, and why both the session sweep/close and the
``WEB3_POOL`` closure must instead be composed directly into
``asgi_app.router.lifespan_context``.

Two call sites in ``server.py`` use this module, and they are intentionally
distinct:

- :func:`log_session_gating_status` is transport-independent and is called
  next to ``_log_pro_api_key_status()`` *before* the ``if run_in_http:``
  branch, so the "configured but inactive" diagnostic still appears on stdio.
- :func:`validate_gated_startup`, :func:`initialize_gated_store`, and
  :func:`build_lifespan` are only relevant in HTTP mode and are invoked from
  inside the existing ``if run_in_http:`` branch.

Runtime policy after startup is degraded-mode only: once the store has
initialized, a sweep fault is logged and swallowed, never raised. The only
fail-fast boundary is startup validation before Uvicorn ever binds a socket.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette

from blockscout_mcp_server import session_store
from blockscout_mcp_server.config import config
from blockscout_mcp_server.session_store import SessionStore, close_store, initialize_store
from blockscout_mcp_server.web3_pool import WEB3_POOL

logger = logging.getLogger(__name__)

# Batch size for a single `sweep_batch` call during a sweep pass. A module-level
# constant (rather than inline literal) so tests can monkeypatch it small to
# exercise multi-batch draining without a huge backlog.
SWEEP_BATCH_SIZE = 1_000


class SessionStartupError(Exception):
    """Raised when gated HTTP startup validation fails (fail-fast, pre-Uvicorn)."""


def validate_gated_startup() -> None:
    """Validate all preconditions for gated HTTP startup.

    Raises:
        SessionStartupError: naming the offending setting, if any precondition
            is not met. Must be called, and must succeed, before
            :func:`initialize_gated_store` — a rejected startup must never
            create a database file.
    """
    if not config.session_db_path:
        raise SessionStartupError(
            "Session gating is enabled (BLOCKSCOUT_SESSION_SECRET is set) but "
            "BLOCKSCOUT_SESSION_DB_PATH is not configured. Set BLOCKSCOUT_SESSION_DB_PATH "
            "to an absolute path for the session store database."
        )

    db_path = Path(config.session_db_path)
    if not db_path.is_absolute():
        raise SessionStartupError(
            f"BLOCKSCOUT_SESSION_DB_PATH must be an absolute filesystem path, got "
            f"{config.session_db_path!r}. An in-memory database (':memory:') contradicts "
            "restart persistence, and a relative path would silently resolve against the "
            "process's working directory."
        )

    if not config.pro_api_key_header:
        raise SessionStartupError(
            "Session gating is enabled (BLOCKSCOUT_SESSION_SECRET is set) but "
            "BLOCKSCOUT_PRO_API_KEY_HEADER is empty. Every gate refusal and outage message "
            "presents a client-supplied PRO API key as the remedy, so the header used to "
            "extract it cannot be disabled on a gated deployment."
        )

    secret_len = len(config.session_secret.encode("utf-8"))
    if secret_len < 32:
        raise SessionStartupError(
            f"BLOCKSCOUT_SESSION_SECRET must be at least 32 bytes (UTF-8 encoded), got "
            f"{secret_len}. This is a fail-fast guard against a typo'd or placeholder "
            "secret, not an entropy check."
        )

    if not config.pro_api_key:
        raise SessionStartupError(
            "Session gating is enabled (BLOCKSCOUT_SESSION_SECRET is set) but "
            "BLOCKSCOUT_PRO_API_KEY is empty. The official server must hold its own PRO API "
            "key to serve free (session-gated) users at all; without it, nearly every "
            "metered call would fail and be refunded before reaching upstream."
        )


def initialize_gated_store() -> SessionStore:
    """Initialize the session store for gated HTTP startup.

    Must be called only after :func:`validate_gated_startup` succeeds, and
    before ``uvicorn.run`` — a store that cannot open at deploy time must
    prevent the server from ever serving.
    """
    return initialize_store(config.session_db_path)


def log_session_gating_status(run_in_http: bool) -> None:
    """Log the session-gating configuration state at startup, for any transport.

    - Secret set and running in HTTP mode: an ``ENABLED`` line with the
      configured db path, max calls, and TTL.
    - Secret set but not running in HTTP mode (stdio): a line stating gating
      is configured but inactive, since it requires HTTP mode. This makes an
      accidentally inherited secret visible even though it has no effect.
    - No secret: a quiet ``disabled`` line at the same log level as the PRO
      API key status line.
    """
    if not config.session_secret:
        logger.info("Session gating: disabled")
        return

    if not run_in_http:
        logger.warning(
            "Session gating: BLOCKSCOUT_SESSION_SECRET is configured but inactive because "
            "it requires HTTP mode (server is running in stdio mode)."
        )
        return

    logger.info(
        "Session gating: ENABLED (db=%s, calls=%s, ttl=%ss)",
        config.session_db_path,
        config.session_max_calls,
        config.session_ttl_seconds,
    )


async def run_sweep_pass() -> None:
    """Run one full sweep pass, draining the expiry backlog in batches.

    Loops ``sweep_batch(SWEEP_BATCH_SIZE)`` until nothing more is deleted,
    yielding the event loop between batches so a large expiry cohort never
    stalls in-flight requests. Never raises: a failure is logged at ERROR and
    swallowed, since the sweep has no caller to answer to and correctness
    never depends on it running (only garbage collection does).
    """
    try:
        store = session_store.get_store()
        while True:
            deleted = store.sweep_batch(SWEEP_BATCH_SIZE)
            if deleted < SWEEP_BATCH_SIZE:
                break
            await asyncio.sleep(0)
    except Exception:
        logger.exception("Session store sweep pass failed; skipping until the next pass.")


async def _periodic_sweep_loop() -> None:
    """Run :func:`run_sweep_pass` once per `config.session_ttl_seconds`, forever."""
    while True:
        await asyncio.sleep(config.session_ttl_seconds)
        await run_sweep_pass()


def build_lifespan(
    original_lifespan: Callable[[Starlette], AbstractAsyncContextManager[None]],
    *,
    gate_enabled: bool,
) -> Callable[[Starlette], AbstractAsyncContextManager[None]]:
    """Compose the app's original lifespan with session-sweep and shutdown wiring.

    Returns a new lifespan callable suitable for assignment to
    ``asgi_app.router.lifespan_context``. On entry, if ``gate_enabled``, runs
    one immediate sweep pass and spawns the periodic sweep task. On exit
    (always inside the original lifespan's context), cancels and awaits the
    sweep task (suppressing its ``CancelledError``), closes the session store
    (a no-op if it was never initialized), and awaits ``WEB3_POOL.close()``.
    """

    @asynccontextmanager
    async def _composed_lifespan(app: Starlette) -> AsyncIterator[None]:
        async with original_lifespan(app):
            sweep_task: asyncio.Task[None] | None = None
            if gate_enabled:
                await run_sweep_pass()
                sweep_task = asyncio.create_task(_periodic_sweep_loop())
            try:
                yield
            finally:
                if sweep_task is not None:
                    sweep_task.cancel()
                    try:
                        await sweep_task
                    except asyncio.CancelledError:
                        pass
                close_store()
                await WEB3_POOL.close()

    return _composed_lifespan


def wire_lifespan(asgi_app: Starlette, *, gate_enabled: bool) -> None:
    """Replace ``asgi_app.router.lifespan_context`` with the composed lifespan.

    Do not use ``add_event_handler`` for any of this — see the module
    docstring for why it silently never runs on this app.
    """
    original_lifespan = asgi_app.router.lifespan_context
    asgi_app.router.lifespan_context = build_lifespan(original_lifespan, gate_enabled=gate_enabled)
