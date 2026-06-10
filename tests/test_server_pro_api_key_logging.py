# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the PRO API key startup diagnostic in server.py."""

import re
from unittest.mock import MagicMock

from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helper-content scenarios (direct calls to _log_pro_api_key_status)
# ---------------------------------------------------------------------------


def test_no_key_logs_warning_with_env_var_name(caplog, monkeypatch):
    """When pro_api_key is empty, the startup diagnostic names BLOCKSCOUT_PRO_API_KEY."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "pro_api_key", "")
    monkeypatch.setattr(server.config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key")

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_pro_api_key_status()

    assert any("BLOCKSCOUT_PRO_API_KEY" in r.message for r in caplog.records)


def test_no_key_log_is_warning_level(caplog, monkeypatch):
    """When pro_api_key is empty, the record is emitted at WARNING level even with client keys enabled."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "pro_api_key", "")
    monkeypatch.setattr(server.config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key")

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_pro_api_key_status()

    matching = [r for r in caplog.records if "BLOCKSCOUT_PRO_API_KEY" in r.message]
    assert matching, "Expected at least one log record mentioning BLOCKSCOUT_PRO_API_KEY"
    assert all(r.levelname == "WARNING" for r in matching)


def test_no_key_log_does_not_mention_client_key_header(caplog, monkeypatch):
    """When pro_api_key is empty, the log must not name the client-key header."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "pro_api_key", "")
    monkeypatch.setattr(server.config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key")

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_pro_api_key_status()

    for record in caplog.records:
        assert "Blockscout-MCP-Pro-Api-Key" not in record.message, "Log must not mention the client-key header name"
        assert "clients may supply" not in record.message.lower(), "Log must not tell clients to supply their own key"


def test_no_key_and_client_keys_disabled_logs_warning(caplog, monkeypatch):
    """When neither a server key nor the client-key header is configured, the diagnostic escalates to WARNING."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "pro_api_key", "")
    monkeypatch.setattr(server.config, "pro_api_key_header", "")

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_pro_api_key_status()

    matching = [r for r in caplog.records if "BLOCKSCOUT_PRO_API_KEY" in r.message]
    assert matching, "Expected at least one log record mentioning BLOCKSCOUT_PRO_API_KEY"
    assert all(r.levelname == "WARNING" for r in matching), "Dead configuration must be logged at WARNING level"


def test_key_configured_logs_confirmation_without_key_value(caplog, monkeypatch):
    """When pro_api_key is set, the log confirms it but does not reveal the value."""
    from blockscout_mcp_server import server

    dummy_key = "secret-key-do-not-log"
    monkeypatch.setattr(server.config, "pro_api_key", dummy_key)

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_pro_api_key_status()

    assert caplog.records, "Expected at least one log record when key is configured"
    assert any("is configured" in r.message for r in caplog.records), (
        "Expected a log record confirming the key is configured"
    )
    for record in caplog.records:
        assert dummy_key not in record.message, "The actual key value must never appear in the log"


# ---------------------------------------------------------------------------
# Startup-wiring scenarios (prove main_command calls the helper)
# ---------------------------------------------------------------------------


def test_http_mode_calls_log_pro_api_key_status(monkeypatch):
    """In HTTP mode, main_command calls _log_pro_api_key_status exactly once."""
    from blockscout_mcp_server import server

    mock_log_status = MagicMock()
    monkeypatch.setattr(server, "_log_pro_api_key_status", mock_log_status)
    # Pin the transport so ambient BLOCKSCOUT_MCP_TRANSPORT cannot change the code path
    monkeypatch.setattr(server.config, "mcp_transport", "")
    monkeypatch.setattr(server.uvicorn, "run", MagicMock())

    result = runner.invoke(server.cli_app, ["--http"])

    assert result.exit_code == 0, f"CLI exited with non-zero code: {result.output}"
    mock_log_status.assert_called_once()


def test_stdio_mode_calls_log_pro_api_key_status(monkeypatch):
    """In stdio mode, main_command calls _log_pro_api_key_status exactly once."""
    import mcp.server.fastmcp

    from blockscout_mcp_server import server

    mock_log_status = MagicMock()
    monkeypatch.setattr(server, "_log_pro_api_key_status", mock_log_status)
    # Pin the transport so an ambient BLOCKSCOUT_MCP_TRANSPORT=http cannot divert
    # this test into the HTTP path, where uvicorn.run is not mocked
    monkeypatch.setattr(server.config, "mcp_transport", "")
    monkeypatch.setattr(mcp.server.fastmcp.FastMCP, "run", MagicMock())

    result = runner.invoke(server.cli_app, [])

    assert result.exit_code == 0, f"CLI exited with non-zero code: {result.output}"
    mock_log_status.assert_called_once()


def test_rejected_invocation_does_not_call_log_pro_api_key_status(monkeypatch):
    """--rest without --http must fail and must NOT call _log_pro_api_key_status."""
    from blockscout_mcp_server import server

    mock_log_status = MagicMock()
    monkeypatch.setattr(server, "_log_pro_api_key_status", mock_log_status)
    # Also ensure mcp_transport is not "http" so the early guard fires
    monkeypatch.setattr(server.config, "mcp_transport", "")

    result = runner.invoke(server.cli_app, ["--rest"])

    assert result.exit_code != 0, "Expected non-zero exit for --rest without --http"
    # Strip ANSI color codes and verify the error message
    output_clean = re.sub(r"\x1b\[[0-9;]*[mK]", "", result.output)
    assert "The --rest flag can only be used with the --http flag." in output_clean
    mock_log_status.assert_not_called()
