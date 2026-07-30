# SPDX-License-Identifier: LicenseRef-Blockscout
"""Startup validation, status-line, and lifespan-wiring tests for the session gate
(issue #442, Phase 9). See `blockscout_mcp_server/session_lifecycle.py` for the
module under test.

Isolation: `pristine_config` (autouse, `tests/conftest.py`) resets every `config`
field to its code default before each test, so each test here only needs to
`monkeypatch.setattr(config, ...)` the handful of fields it cares about — no
`importlib.reload` dance is needed since none of these tests rebuild the config
module itself.

Thread ownership (load-bearing, see the docstring of
`tests/test_session_gate_http_transport.py` for the general rule): the session
store keeps `check_same_thread=True`, so a store initialized on one thread must
only be touched from that same thread. `CliRunner.invoke` runs `main_command`
synchronously on the pytest thread, so the store it initializes can safely be
driven by an `asyncio.run(...)` call made right after `invoke()` returns, on that
same thread. This file therefore does NOT use `starlette.testclient.TestClient`
for the lifespan tests below: `TestClient` enters the lifespan from an AnyIO
portal thread, which would violate that constraint. Instead, it captures the
exact ASGI app Uvicorn would have received (by patching `uvicorn.run`) and enters
`app.router.lifespan_context(app)` directly via `asyncio.run` on the test's own
thread.
"""

from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from blockscout_mcp_server import server, session_lifecycle, session_store
from blockscout_mcp_server.config import config
from blockscout_mcp_server.session_lifecycle import SessionStartupError
from blockscout_mcp_server.web3_pool import WEB3_POOL

runner = CliRunner()

_VALID_SECRET = "s" * 32  # exactly 32 bytes: the boundary-pass case
_VALID_HEADER = "Blockscout-MCP-Pro-Api-Key"
_VALID_KEY = "test-pro-api-key"


def _set_valid_gated_config(monkeypatch, db_path: str) -> None:
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "session_db_path", db_path)
    monkeypatch.setattr(config, "pro_api_key_header", _VALID_HEADER)
    monkeypatch.setattr(config, "pro_api_key", _VALID_KEY)


def _invoke_http_capturing_app(extra_args: list[str] | None = None):
    """Invoke `main_command` in HTTP mode with `uvicorn.run` patched to capture the
    exact ASGI app it would have served, instead of actually binding a socket."""
    captured: dict = {}

    def _capture(app, **kwargs):
        captured["app"] = app

    with patch("uvicorn.run", side_effect=_capture) as mock_run:
        result = runner.invoke(server.cli_app, ["--http", *(extra_args or [])])
    return result, captured.get("app"), mock_run


def _reset_session_manager() -> None:
    """Clear `server.mcp`'s cached `StreamableHTTPSessionManager`.

    `mcp.streamable_http_app()` memoizes the manager on first call and it can only be
    `.run()` once ever afterwards. Every test that actually drives
    `app.router.lifespan_context(app)` to completion must reset this first, or it dies
    with "StreamableHTTPSessionManager .run() can only be called once per instance" —
    a leftover from whichever earlier test in this session happened to run first.
    """
    server.mcp._session_manager = None


def _invoke_stdio():
    """Invoke `main_command` in stdio mode with `FastMCP.run` patched so the CLI
    invocation returns immediately instead of blocking on real stdin/stdout, mirroring
    `test_stdio_mode_works` in `tests/test_server.py`."""
    with patch("mcp.server.fastmcp.FastMCP.run"):
        return runner.invoke(server.cli_app, [])


# ---------------------------------------------------------------------------
# Gated-startup validation
# ---------------------------------------------------------------------------


def test_empty_db_path_fails_gated_startup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "session_db_path", "")
    monkeypatch.setattr(config, "pro_api_key_header", _VALID_HEADER)
    monkeypatch.setattr(config, "pro_api_key", _VALID_KEY)

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code != 0
    assert isinstance(result.exception, SessionStartupError)
    assert "BLOCKSCOUT_SESSION_DB_PATH" in str(result.exception)
    mock_run.assert_not_called()
    assert app is None


@pytest.mark.parametrize("bad_path", [":memory:", "relative/sessions.db"])
def test_non_absolute_db_path_fails_gated_startup(monkeypatch, bad_path):
    _set_valid_gated_config(monkeypatch, bad_path)

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code != 0
    assert isinstance(result.exception, SessionStartupError)
    assert "BLOCKSCOUT_SESSION_DB_PATH" in str(result.exception)
    mock_run.assert_not_called()
    assert app is None


def test_missing_directory_fails_gated_startup(monkeypatch, tmp_path):
    missing_dir = tmp_path / "does-not-exist"
    _set_valid_gated_config(monkeypatch, str(missing_dir / "sessions.db"))

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code != 0
    assert not missing_dir.exists()
    mock_run.assert_not_called()
    assert app is None
    assert isinstance(result.exception, session_store.SessionStoreInitializationError)
    assert str(missing_dir) in str(result.exception)
    assert "BLOCKSCOUT_SESSION_DB_PATH" in str(result.exception)


def test_empty_pro_api_key_header_fails_gated_startup(monkeypatch, tmp_path):
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "session_db_path", str(db_path))
    monkeypatch.setattr(config, "pro_api_key_header", "")
    monkeypatch.setattr(config, "pro_api_key", _VALID_KEY)

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code != 0
    assert isinstance(result.exception, SessionStartupError)
    assert "BLOCKSCOUT_PRO_API_KEY_HEADER" in str(result.exception)
    assert not db_path.exists()
    mock_run.assert_not_called()


def test_empty_pro_api_key_header_ungated_http_still_starts(monkeypatch):
    monkeypatch.setattr(config, "session_secret", "")
    monkeypatch.setattr(config, "pro_api_key_header", "")

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert app is not None


def test_empty_pro_api_key_header_stdio_with_secret_only_logs(monkeypatch, caplog):
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "pro_api_key_header", "")

    with caplog.at_level(logging.WARNING):
        result = _invoke_stdio()

    assert result.exit_code == 0
    assert "requires HTTP mode" in caplog.text


@pytest.mark.parametrize("secret_len", [31, 0])
def test_short_secret_fails_gated_startup(monkeypatch, tmp_path, secret_len):
    db_path = tmp_path / "sessions.db"
    secret = "s" * secret_len if secret_len else ""
    monkeypatch.setattr(config, "session_secret", secret)
    monkeypatch.setattr(config, "session_db_path", str(db_path))
    monkeypatch.setattr(config, "pro_api_key_header", _VALID_HEADER)
    monkeypatch.setattr(config, "pro_api_key", _VALID_KEY)

    result, app, mock_run = _invoke_http_capturing_app()

    if secret_len == 0:
        # An empty secret means the gate is off entirely (not a startup failure).
        assert result.exit_code == 0
        mock_run.assert_called_once()
    else:
        assert result.exit_code != 0
        assert isinstance(result.exception, SessionStartupError)
        assert "BLOCKSCOUT_SESSION_SECRET" in str(result.exception)
        assert not db_path.exists()
        mock_run.assert_not_called()


def test_exactly_32_byte_secret_passes_boundary(monkeypatch, tmp_path):
    db_path = tmp_path / "sessions.db"
    assert len(_VALID_SECRET.encode("utf-8")) == 32
    _set_valid_gated_config(monkeypatch, str(db_path))

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert db_path.exists()


def test_short_secret_stdio_only_logs_inactive(monkeypatch, caplog):
    monkeypatch.setattr(config, "session_secret", "short")

    with caplog.at_level(logging.WARNING):
        result = _invoke_stdio()

    assert result.exit_code == 0
    assert "requires HTTP mode" in caplog.text


def test_empty_pro_api_key_fails_gated_startup(monkeypatch, tmp_path):
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "session_db_path", str(db_path))
    monkeypatch.setattr(config, "pro_api_key_header", _VALID_HEADER)
    monkeypatch.setattr(config, "pro_api_key", "")

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code != 0
    assert isinstance(result.exception, SessionStartupError)
    assert "BLOCKSCOUT_PRO_API_KEY" in str(result.exception)
    assert not db_path.exists()
    mock_run.assert_not_called()


def test_empty_pro_api_key_ungated_http_still_starts(monkeypatch):
    monkeypatch.setattr(config, "session_secret", "")
    monkeypatch.setattr(config, "pro_api_key", "")

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_empty_pro_api_key_stdio_with_secret_only_logs(monkeypatch, caplog):
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "pro_api_key", "")

    with caplog.at_level(logging.WARNING):
        result = _invoke_stdio()

    assert result.exit_code == 0
    assert "requires HTTP mode" in caplog.text


def test_valid_config_initializes_store_and_logs_enabled(monkeypatch, tmp_path, caplog):
    db_path = tmp_path / "sessions.db"
    _set_valid_gated_config(monkeypatch, str(db_path))

    with caplog.at_level(logging.INFO):
        result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    assert db_path.exists()
    mock_run.assert_called_once()
    assert app is not None
    assert "Session gating: ENABLED" in caplog.text
    assert str(db_path) in caplog.text
    assert str(config.session_max_calls) in caplog.text
    assert str(config.session_ttl_seconds) in caplog.text

    session_store.close_store()


def test_no_secret_disables_gate_and_skips_store_init(monkeypatch, caplog):
    monkeypatch.setattr(config, "session_secret", "")

    with (
        patch("blockscout_mcp_server.server.initialize_gated_store") as mock_init,
        caplog.at_level(logging.INFO),
    ):
        result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    mock_run.assert_called_once()
    mock_init.assert_not_called()
    assert "Session gating: disabled" in caplog.text


def test_secret_set_stdio_mode_skips_store_init_and_logs_inactive(monkeypatch, caplog):
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)

    with (
        patch("blockscout_mcp_server.server.initialize_gated_store") as mock_init,
        caplog.at_level(logging.WARNING),
    ):
        result = _invoke_stdio()

    assert result.exit_code == 0
    mock_init.assert_not_called()
    assert "Session gating" in caplog.text
    assert "requires HTTP mode" in caplog.text


# ---------------------------------------------------------------------------
# Lifespan execution
# ---------------------------------------------------------------------------


def test_gated_lifespan_sweeps_and_tears_down_cleanly(monkeypatch, tmp_path):
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    _set_valid_gated_config(monkeypatch, str(db_path))
    _reset_session_manager()

    result, app, mock_run = _invoke_http_capturing_app()
    assert result.exit_code == 0
    assert app is not None

    store = session_store.get_store()
    # An expired row (created well before the 100s TTL) must be gone once the
    # immediate on-entry sweep pass runs.
    store.check_and_increment("expired-session", created_at=0)
    store.check_and_increment("fresh-session", created_at=int(time.time()))

    web3_close_mock = AsyncMock()
    monkeypatch.setattr(WEB3_POOL, "close", web3_close_mock)

    async def _run():
        outer_task = asyncio.current_task()
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)
            other_tasks = [t for t in asyncio.all_tasks() if t is not outer_task]
            assert len(other_tasks) == 1, "expected exactly one periodic sweep task"
            sweep_task = other_tasks[0]
            assert not sweep_task.done()

            assert store.get_calls("expired-session") == 0
            assert store.get_calls("fresh-session") == 1
        return sweep_task

    sweep_task = asyncio.run(_run())

    assert sweep_task.done()
    assert sweep_task.cancelled() or sweep_task.exception() is None
    web3_close_mock.assert_awaited_once()
    with pytest.raises(RuntimeError):
        session_store.get_store()


def test_ungated_lifespan_runs_cleanly_without_sweep(monkeypatch):
    monkeypatch.setattr(config, "session_secret", "")
    _reset_session_manager()

    result, app, mock_run = _invoke_http_capturing_app()
    assert result.exit_code == 0
    assert app is not None

    web3_close_mock = AsyncMock()
    monkeypatch.setattr(WEB3_POOL, "close", web3_close_mock)

    async def _run():
        outer_task = asyncio.current_task()
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)
            other_tasks = [t for t in asyncio.all_tasks() if t is not outer_task]
            assert other_tasks == [], "no sweep task should exist when the gate is disabled"

    asyncio.run(_run())

    web3_close_mock.assert_awaited_once()
    # close_store() must have run as the Phase 2 no-op guarantee (never initialized).
    with pytest.raises(RuntimeError):
        session_store.get_store()


def test_sweep_pass_fault_is_logged_and_does_not_raise(monkeypatch, caplog):
    class _ExplodingStore:
        def sweep_batch(self, limit):
            raise RuntimeError("boom")

    monkeypatch.setattr(session_store, "get_store", lambda: _ExplodingStore())

    with caplog.at_level(logging.ERROR):
        asyncio.run(session_lifecycle.run_sweep_pass())

    assert "sweep" in caplog.text.lower()
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_periodic_sweep_loop_continues_past_failing_pass(monkeypatch, caplog):
    """The periodic loop itself (not just `run_sweep_pass`) must survive a faulting
    pass: it logs at ERROR and keeps iterating, never propagating the exception out
    of the task. Isolated from the lifespan/server entirely — a mocked store and a
    near-zero TTL are enough to drive several iterations quickly."""
    monkeypatch.setattr(config, "session_ttl_seconds", 0)

    call_count = {"n": 0}

    class _ExplodingStore:
        def sweep_batch(self, limit):
            call_count["n"] += 1
            raise RuntimeError("boom")

    monkeypatch.setattr(session_store, "get_store", lambda: _ExplodingStore())

    async def _run():
        with caplog.at_level(logging.ERROR):
            task = asyncio.create_task(session_lifecycle._periodic_sweep_loop())
            try:
                for _ in range(1000):
                    if call_count["n"] >= 3:
                        break
                    await asyncio.sleep(0)
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return task

    task = asyncio.run(_run())

    assert call_count["n"] >= 3, "loop must keep calling sweep_batch across multiple passes"
    assert task.done()
    # The task must have ended via our cancellation, not via the RuntimeError leaking
    # out of `_periodic_sweep_loop` (which would show up as task.exception()).
    assert task.cancelled() or task.exception() is None
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) >= 3, "each faulting pass must log at ERROR"


def test_first_pass_fault_does_not_abort_lifespan_entry(monkeypatch, tmp_path, caplog):
    db_path = tmp_path / "sessions.db"
    _set_valid_gated_config(monkeypatch, str(db_path))
    _reset_session_manager()

    result, app, mock_run = _invoke_http_capturing_app()
    assert result.exit_code == 0
    assert app is not None

    web3_close_mock = AsyncMock()
    monkeypatch.setattr(WEB3_POOL, "close", web3_close_mock)

    # Make the store's `sweep_batch` raise on the very first call the immediate
    # on-entry pass makes; `run_sweep_pass` swallows the fault internally, so the
    # lifespan must still enter cleanly and the periodic task must still be alive.
    store = session_store.get_store()
    real_sweep_batch = store.sweep_batch
    batch_calls = {"n": 0}

    def _sweep_batch(limit):
        batch_calls["n"] += 1
        if batch_calls["n"] == 1:
            raise RuntimeError("first pass exploded")
        return real_sweep_batch(limit)

    monkeypatch.setattr(store, "sweep_batch", _sweep_batch)

    async def _run():
        outer_task = asyncio.current_task()
        with caplog.at_level(logging.ERROR):
            async with app.router.lifespan_context(app):
                await asyncio.sleep(0)
                other_tasks = [t for t in asyncio.all_tasks() if t is not outer_task]
                assert len(other_tasks) == 1
                assert not other_tasks[0].done()
        return other_tasks[0]

    sweep_task = asyncio.run(_run())

    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert sweep_task.done()
    web3_close_mock.assert_awaited_once()


def test_sweep_pass_drains_backlog_in_batches(monkeypatch, tmp_path):
    monkeypatch.setattr(session_lifecycle, "SWEEP_BATCH_SIZE", 2)
    monkeypatch.setattr(config, "session_ttl_seconds", 100)

    store = session_store.initialize_store(str(tmp_path / "sessions.db"))
    for i in range(5):
        store.check_and_increment(f"expired-{i}", created_at=0)

    real_sweep_batch = store.sweep_batch
    call_count = {"n": 0}

    def _counting_sweep_batch(limit):
        call_count["n"] += 1
        return real_sweep_batch(limit)

    monkeypatch.setattr(store, "sweep_batch", _counting_sweep_batch)
    monkeypatch.setattr(session_store, "get_store", lambda: store)

    asyncio.run(session_lifecycle.run_sweep_pass())

    # 5 rows with a batch size of 2: batches of 2, 2, 1 (the last returns < limit and
    # stops the loop) = 3 calls.
    assert call_count["n"] == 3
    for i in range(5):
        assert store.get_calls(f"expired-{i}") == 0

    session_store.close_store()
