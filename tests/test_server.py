"""Tests for the main server CLI and application logic."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from blockscout_mcp_server.server import cli_app

runner = CliRunner()


@patch("uvicorn.run")
def test_cli_http_mode(mock_uvicorn_run: MagicMock):
    """Verify that --http flag starts the original MCP http app."""
    result = runner.invoke(cli_app, ["--http"])
    assert result.exit_code == 0
    assert "Starting Blockscout MCP Server in HTTP Streamable mode" in result.stdout
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.args[0] != "blockscout_mcp_server.asgi:app"
    assert not isinstance(mock_uvicorn_run.call_args.args[0], str)


@patch("uvicorn.run")
def test_cli_http_rest_mode(mock_uvicorn_run: MagicMock):
    """Verify that --http --rest flags start the new unified ASGI app."""
    result = runner.invoke(cli_app, ["--http", "--rest"])
    assert result.exit_code == 0
    assert "Starting Blockscout MCP Server with REST API" in result.stdout
    mock_uvicorn_run.assert_called_once_with("blockscout_mcp_server.asgi:app", host="127.0.0.1", port=8000)


def test_cli_rest_without_http_fails():
    """Verify that --rest without --http raises an error."""
    result = runner.invoke(cli_app, ["--rest"])
    assert result.exit_code == 1
    assert "Error: --rest flag requires --http flag" in result.stdout


@patch("blockscout_mcp_server.server.mcp.run")
@patch("uvicorn.run")
def test_cli_stdio_mode(mock_uvicorn_run: MagicMock, mock_mcp_run: MagicMock):
    """Verify that no flags run in stdio mode (and don't call uvicorn)."""
    result = runner.invoke(cli_app, [])
    assert result.exit_code == 0
    mock_uvicorn_run.assert_not_called()
    mock_mcp_run.assert_called_once()


@pytest.mark.parametrize(
    "args, expected_host, expected_port",
    [
        (["--http", "--http-host", "0.0.0.0"], "0.0.0.0", 8000),
        (["--http", "--http-port", "9999"], "127.0.0.1", 9999),
        (["--http", "--rest", "--http-host", "test.host"], "test.host", 8000),
    ],
)
@patch("uvicorn.run")
def test_cli_http_host_port_args(mock_uvicorn_run: MagicMock, args, expected_host, expected_port):
    """Verify that http-host and http-port arguments are passed to uvicorn."""
    result = runner.invoke(cli_app, args)
    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["host"] == expected_host
    assert mock_uvicorn_run.call_args.kwargs["port"] == expected_port
