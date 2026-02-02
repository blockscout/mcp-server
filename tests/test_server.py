import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from blockscout_mcp_server.constants import DEFAULT_HTTP_PORT

runner = CliRunner()


def test_rest_flag_without_http_fails():
    """Verify that using --rest without --http raises a CLI error."""
    from blockscout_mcp_server.server import cli_app

    result = runner.invoke(cli_app, ["--rest"])
    assert result.exit_code != 0
    # Typer may add ANSI color codes to the error message; strip them for a stable assertion.
    output_clean = re.sub(r"\x1b\[[0-9;]*[mK]", "", result.output)
    assert "The --rest flag can only be used with the --http flag." in output_clean


@patch("uvicorn.run")
@patch("blockscout_mcp_server.server.register_api_routes")
def test_http_and_rest_flags_call_register_routes(mock_register_routes, mock_uvicorn_run):
    """Verify that --http and --rest together call the route registration function."""
    from blockscout_mcp_server import server

    result = runner.invoke(server.cli_app, ["--http", "--rest"])

    assert result.exit_code == 0
    mock_register_routes.assert_called_once()
    mock_uvicorn_run.assert_called_once()


@patch("uvicorn.run")
@patch("blockscout_mcp_server.server.register_api_routes", create=True)
def test_http_only_does_not_register_rest_routes(mock_register_routes, mock_uvicorn_run):
    """Verify that --http alone does not call the route registration function."""
    from blockscout_mcp_server.server import cli_app

    result = runner.invoke(cli_app, ["--http"])

    assert result.exit_code == 0
    mock_register_routes.assert_not_called()
    mock_uvicorn_run.assert_called_once()


@patch("mcp.server.fastmcp.FastMCP.run")
def test_stdio_mode_works(mock_mcp_run):
    """Verify that the default stdio mode runs correctly."""
    from blockscout_mcp_server.server import cli_app

    result = runner.invoke(cli_app, [])
    assert result.exit_code == 0
    mock_mcp_run.assert_called_once()


@patch("pathlib.Path.exists", return_value=True)
def test_env_var_triggers_http_mode(mock_exists, monkeypatch):
    """Verify that setting BLOCKSCOUT_MCP_TRANSPORT=http starts the server in HTTP mode."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_transport", "HTTP")
    mock_run = MagicMock()
    monkeypatch.setattr(server.uvicorn, "run", mock_run)

    result = runner.invoke(server.cli_app, [])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["host"] == "0.0.0.0"


@patch("pathlib.Path.exists", return_value=False)
def test_env_var_http_mode_non_container(mock_exists, monkeypatch):
    """Env var enables HTTP but non-container uses default host."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_transport", "http")
    mock_run = MagicMock()
    monkeypatch.setattr(server.uvicorn, "run", mock_run)

    result = runner.invoke(server.cli_app, [])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["host"] == "127.0.0.1"


def test_dev_json_response_default_false(monkeypatch):
    from importlib import reload

    monkeypatch.delenv("BLOCKSCOUT_DEV_JSON_RESPONSE", raising=False)
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.dev_json_response is False
    reload(cfg)


def test_dev_json_response_true(monkeypatch):
    from importlib import reload

    monkeypatch.setenv("BLOCKSCOUT_DEV_JSON_RESPONSE", "true")
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.dev_json_response is True

    monkeypatch.delenv("BLOCKSCOUT_DEV_JSON_RESPONSE")
    reload(cfg)


def test_dev_json_response_false(monkeypatch):
    from importlib import reload

    monkeypatch.setenv("BLOCKSCOUT_DEV_JSON_RESPONSE", "false")
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.dev_json_response is False

    monkeypatch.delenv("BLOCKSCOUT_DEV_JSON_RESPONSE")
    reload(cfg)


def test_port_from_env_variable(monkeypatch):
    monkeypatch.setenv("PORT", "9999")
    from importlib import reload

    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.port == 9999

    monkeypatch.delenv("PORT")
    reload(cfg)


@patch("uvicorn.run")
def test_cli_flag_overrides_env_port(mock_uvicorn_run, monkeypatch):
    monkeypatch.setenv("PORT", "9001")
    from importlib import reload

    from blockscout_mcp_server import config as cfg

    reload(cfg)
    from blockscout_mcp_server import server

    reload(server)

    result = runner.invoke(server.cli_app, ["--http", "--http-port", "9000"])

    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == 9000
    assert "Both --http-port (9000) and PORT (9001) are set" in result.output

    monkeypatch.delenv("PORT")
    reload(cfg)
    reload(server)


@patch("uvicorn.run")
def test_same_port_no_warning(mock_uvicorn_run, monkeypatch, capsys):
    monkeypatch.setenv("PORT", "9003")
    from importlib import reload

    from blockscout_mcp_server import config as cfg

    reload(cfg)
    from blockscout_mcp_server import server

    reload(server)

    server.main_command(http=True, http_port=9003)

    captured = capsys.readouterr()
    assert "Both --http-port" not in captured.out
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == 9003

    monkeypatch.delenv("PORT")
    reload(cfg)
    reload(server)


@patch("uvicorn.run")
def test_env_port_used_when_flag_absent(mock_uvicorn_run, monkeypatch):
    monkeypatch.setenv("PORT", "9002")
    from importlib import reload

    from blockscout_mcp_server import config as cfg

    reload(cfg)
    from blockscout_mcp_server import server

    reload(server)

    result = runner.invoke(server.cli_app, ["--http"])

    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == 9002

    monkeypatch.delenv("PORT")
    reload(cfg)
    reload(server)


@patch("uvicorn.run")
def test_default_port_used_when_no_flag_or_env(mock_uvicorn_run, monkeypatch):
    from importlib import reload

    from blockscout_mcp_server import config as cfg

    reload(cfg)
    from blockscout_mcp_server import server

    reload(server)

    result = runner.invoke(server.cli_app, ["--http"])

    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == DEFAULT_HTTP_PORT

    reload(cfg)
    reload(server)
