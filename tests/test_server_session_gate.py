# SPDX-License-Identifier: LicenseRef-Blockscout
"""Startup validation tests for the session gate (issue #442, Phase 9). See
`blockscout_mcp_server/session_lifecycle.py` for the module under test.

Split out of the original `tests/test_server_session_gate.py` to keep both files
comfortably under the ~500 LOC guideline; the sibling
`tests/test_server_session_gate_lifespan.py` covers the real-lifespan and
periodic-sweep-task tests instead. This file covers: gated-startup validation of
each config field (secret, db path, pro API key header/key) and the ungated/stdio
fallback logging behavior.

Isolation: `pristine_config` (autouse, `tests/conftest.py`) resets every `config`
field to its code default before each test, so each test here only needs to
`monkeypatch.setattr(config, ...)` the handful of fields it cares about — no
`importlib.reload` dance is needed since none of these tests rebuild the config
module itself.

CLI contract: `main_command` catches `SessionStartupError` /
`SessionStoreInitializationError` and converts them to a clean stderr message
plus exit code 1 (no traceback), so the failing-startup tests here assert on
`result.exit_code` and `result.stderr`, never on `result.exception`.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from blockscout_mcp_server import server, session_store
from blockscout_mcp_server.config import config

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

    assert result.exit_code == 1
    assert "Session gating startup failed" in result.stderr
    assert "BLOCKSCOUT_SESSION_DB_PATH" in result.stderr
    mock_run.assert_not_called()
    assert app is None


@pytest.mark.parametrize("bad_path", [":memory:", "relative/sessions.db"])
def test_non_absolute_db_path_fails_gated_startup(monkeypatch, bad_path):
    _set_valid_gated_config(monkeypatch, bad_path)

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 1
    assert "Session gating startup failed" in result.stderr
    assert "BLOCKSCOUT_SESSION_DB_PATH" in result.stderr
    mock_run.assert_not_called()
    assert app is None


def test_missing_directory_fails_gated_startup(monkeypatch, tmp_path):
    missing_dir = tmp_path / "does-not-exist"
    _set_valid_gated_config(monkeypatch, str(missing_dir / "sessions.db"))

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 1
    assert not missing_dir.exists()
    mock_run.assert_not_called()
    assert app is None
    assert "Session gating startup failed" in result.stderr
    assert str(missing_dir) in result.stderr
    assert "BLOCKSCOUT_SESSION_DB_PATH" in result.stderr


def test_empty_pro_api_key_header_fails_gated_startup(monkeypatch, tmp_path):
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(config, "session_secret", _VALID_SECRET)
    monkeypatch.setattr(config, "session_db_path", str(db_path))
    monkeypatch.setattr(config, "pro_api_key_header", "")
    monkeypatch.setattr(config, "pro_api_key", _VALID_KEY)

    result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 1
    assert "Session gating startup failed" in result.stderr
    assert "BLOCKSCOUT_PRO_API_KEY_HEADER" in result.stderr
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
        assert result.exit_code == 1
        assert "Session gating startup failed" in result.stderr
        assert "BLOCKSCOUT_SESSION_SECRET" in result.stderr
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

    assert result.exit_code == 1
    assert "Session gating startup failed" in result.stderr
    assert "BLOCKSCOUT_PRO_API_KEY" in result.stderr
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
    monkeypatch.setattr(config, "session_mcp_max_calls", 7)
    monkeypatch.setattr(config, "session_rest_max_calls", 3)

    with caplog.at_level(logging.INFO):
        result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    assert db_path.exists()
    mock_run.assert_called_once()
    assert app is not None
    assert "Session gating: ENABLED" in caplog.text
    assert str(db_path) in caplog.text
    assert "mcp_calls=7" in caplog.text
    assert "rest_calls=3" in caplog.text
    assert str(config.session_ttl_seconds) in caplog.text
    # Sweep interval is unset here, so the logged cadence falls back to the TTL.
    assert f"sweep={config.session_ttl_seconds}s" in caplog.text

    session_store.close_store()


def test_both_ceilings_zero_logs_warning(monkeypatch, tmp_path, caplog):
    db_path = tmp_path / "sessions.db"
    _set_valid_gated_config(monkeypatch, str(db_path))
    monkeypatch.setattr(config, "session_mcp_max_calls", 0)
    monkeypatch.setattr(config, "session_rest_max_calls", 0)

    with caplog.at_level(logging.INFO):
        result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert "Session gating: ENABLED" in caplog.text
    assert any(record.levelno == logging.WARNING and "both" in record.getMessage().lower() for record in caplog.records)

    session_store.close_store()


@pytest.mark.parametrize(
    ("mcp_max_calls", "rest_max_calls"),
    [(0, 5), (5, 0)],
)
def test_one_ceiling_zero_does_not_log_warning(monkeypatch, tmp_path, caplog, mcp_max_calls, rest_max_calls):
    db_path = tmp_path / "sessions.db"
    _set_valid_gated_config(monkeypatch, str(db_path))
    monkeypatch.setattr(config, "session_mcp_max_calls", mcp_max_calls)
    monkeypatch.setattr(config, "session_rest_max_calls", rest_max_calls)

    with caplog.at_level(logging.INFO):
        result, app, mock_run = _invoke_http_capturing_app()

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert "Session gating: ENABLED" in caplog.text
    assert not any(record.levelno == logging.WARNING for record in caplog.records)

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
