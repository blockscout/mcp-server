import re
import sys
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

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
def test_http_and_rest_flags_call_register_routes(mock_uvicorn_run):
    """Verify that --http and --rest together call the route registration function."""
    mock_routes_module = MagicMock()
    sys.modules["blockscout_mcp_server.api.routes"] = mock_routes_module
    from blockscout_mcp_server.server import cli_app

    result = runner.invoke(cli_app, ["--http", "--rest"])

    assert result.exit_code == 0
    mock_routes_module.register_api_routes.assert_called_once()
    mock_uvicorn_run.assert_called_once()
    del sys.modules["blockscout_mcp_server.api.routes"]


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
