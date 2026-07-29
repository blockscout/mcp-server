# SPDX-License-Identifier: LicenseRef-Blockscout
import importlib
import re
import sys
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

import blockscout_mcp_server.config
from blockscout_mcp_server.config import ServerConfig
from blockscout_mcp_server.constants import DEFAULT_HTTP_PORT

runner = CliRunner()


def _restore_canonical_config(canonical: ServerConfig) -> None:
    """Reassign the `config` module attribute (and `server.config`, if loaded) to `canonical`.

    Each `importlib.reload(cfg)` in this module rebuilds `blockscout_mcp_server.config`,
    re-executing `config = ServerConfig()` and publishing a brand-new object as the module
    attribute; a subsequent `importlib.reload(server)` then re-binds `server.config` to that
    new object too. Phase 1's `pristine_config` fixture only pins the *original* singleton
    that every tool module bound at import time, so a reload-based test that doesn't repair
    this leaves the module attribute pointing at an unpinned replacement for the rest of the
    session — silently escaping `pristine_config` for any code that resolves `config` through
    the module attribute at runtime. Restoring the canonical object on teardown keeps the
    "one pinned singleton" contract (see the identity contract test in `tests/conftest.py`
    / Phase 1) intact across the whole session.
    """
    blockscout_mcp_server.config.config = canonical
    server_module = sys.modules.get("blockscout_mcp_server.server")
    if server_module is not None:
        server_module.config = canonical


@pytest.fixture(autouse=True)
def _isolate_dotenv_and_singleton(monkeypatch, tmp_path):
    """Isolate `.env` reads and repair the `config` singleton identity for every test here.

    Several tests in this module rebuild the config via `importlib.reload(cfg)`, which
    re-executes `config = ServerConfig()` — a fresh object built from the environment
    **and** from `env_file=".env"`, which pydantic-settings resolves relative to the
    current working directory. Phase 1's `pristine_config` fixture closes the env-var
    channel for these reloads, but nothing stops the file read: a developer whose `.env`
    sets, say, `BLOCKSCOUT_DEV_JSON_RESPONSE=true` would still see
    `test_dev_json_response_default_false` fail. `monkeypatch.chdir(tmp_path)` points the
    relative `".env"` lookup at an empty directory, so every reload builds the config from
    code defaults plus whatever the test itself `setenv`-ed.

    Separately, each reload publishes a *new* `ServerConfig` object as the `config` module
    attribute, replacing the canonical singleton that `pristine_config` pins. Left alone,
    that replacement outlives the test and is never repinned. Capture the canonical object
    up front and restore it via `_restore_canonical_config` on teardown so later tests keep
    seeing the one pinned singleton.
    """
    canonical = blockscout_mcp_server.config.config
    monkeypatch.chdir(tmp_path)
    yield
    _restore_canonical_config(canonical)


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
    monkeypatch.delenv("BLOCKSCOUT_DEV_JSON_RESPONSE", raising=False)
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    assert cfg.config.dev_json_response is False
    importlib.reload(cfg)


def test_dev_json_response_true(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_DEV_JSON_RESPONSE", "true")
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    assert cfg.config.dev_json_response is True

    monkeypatch.delenv("BLOCKSCOUT_DEV_JSON_RESPONSE")
    importlib.reload(cfg)


def test_dev_json_response_false(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_DEV_JSON_RESPONSE", "false")
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    assert cfg.config.dev_json_response is False

    monkeypatch.delenv("BLOCKSCOUT_DEV_JSON_RESPONSE")
    importlib.reload(cfg)


def test_port_from_env_variable(monkeypatch):
    monkeypatch.setenv("PORT", "9999")
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    assert cfg.config.port == 9999

    monkeypatch.delenv("PORT")
    importlib.reload(cfg)


@patch("uvicorn.run")
def test_cli_flag_overrides_env_port(mock_uvicorn_run, monkeypatch):
    monkeypatch.setenv("PORT", "9001")
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    from blockscout_mcp_server import server

    importlib.reload(server)

    result = runner.invoke(server.cli_app, ["--http", "--http-port", "9000"])

    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == 9000
    assert "Both --http-port (9000) and PORT (9001) are set" in result.output

    monkeypatch.delenv("PORT")
    importlib.reload(cfg)
    importlib.reload(server)


@patch("uvicorn.run")
def test_same_port_no_warning(mock_uvicorn_run, monkeypatch, capsys):
    monkeypatch.setenv("PORT", "9003")
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    from blockscout_mcp_server import server

    importlib.reload(server)

    server.main_command(http=True, http_port=9003)

    captured = capsys.readouterr()
    assert "Both --http-port" not in captured.out
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == 9003

    monkeypatch.delenv("PORT")
    importlib.reload(cfg)
    importlib.reload(server)


@patch("uvicorn.run")
def test_env_port_used_when_flag_absent(mock_uvicorn_run, monkeypatch):
    monkeypatch.setenv("PORT", "9002")
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    from blockscout_mcp_server import server

    importlib.reload(server)

    result = runner.invoke(server.cli_app, ["--http"])

    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == 9002

    monkeypatch.delenv("PORT")
    importlib.reload(cfg)
    importlib.reload(server)


@patch("uvicorn.run")
def test_default_port_used_when_no_flag_or_env(mock_uvicorn_run, monkeypatch):
    from blockscout_mcp_server import config as cfg

    importlib.reload(cfg)
    from blockscout_mcp_server import server

    importlib.reload(server)

    result = runner.invoke(server.cli_app, ["--http"])

    assert result.exit_code == 0
    mock_uvicorn_run.assert_called_once()
    assert mock_uvicorn_run.call_args.kwargs["port"] == DEFAULT_HTTP_PORT

    importlib.reload(cfg)
    importlib.reload(server)


def test_restore_canonical_config_repairs_singleton_identity():
    """Prove the reload hazard is real, and that `_restore_canonical_config` repairs it."""
    from blockscout_mcp_server import config as cfg
    from blockscout_mcp_server import server

    canonical = blockscout_mcp_server.config.config

    importlib.reload(cfg)
    importlib.reload(server)
    assert blockscout_mcp_server.config.config is not canonical

    _restore_canonical_config(canonical)

    assert blockscout_mcp_server.config.config is canonical
    assert blockscout_mcp_server.server.config is canonical


def test_split_env_list_none():
    from blockscout_mcp_server import server

    assert server._split_env_list(None) == []


def test_split_env_list_empty_string():
    from blockscout_mcp_server import server

    assert server._split_env_list("") == []


def test_split_env_list_single_value():
    from blockscout_mcp_server import server

    assert server._split_env_list("example.ngrok-free.app") == ["example.ngrok-free.app"]


def test_split_env_list_multiple_values():
    from blockscout_mcp_server import server

    assert server._split_env_list("one, two , ,three") == ["one", "two", "three"]


@pytest.mark.parametrize("http_host", ["127.0.0.1", "localhost", "::1", "[::1]"])
def test_resolve_transport_security_localhost_no_env_vars(monkeypatch, http_host):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "")

    settings = server._resolve_transport_security(http_host)

    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    assert settings.allowed_origins == ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def test_resolve_transport_security_non_localhost_no_env_vars(monkeypatch):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "")

    settings = server._resolve_transport_security("0.0.0.0")

    assert settings.enable_dns_rebinding_protection is False


def test_transport_security_settings_allowed_hosts(monkeypatch):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "host1, host2")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "")

    settings = server._resolve_transport_security("0.0.0.0")
    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["host1", "host2"]
    assert settings.allowed_origins == []


def test_transport_security_settings_allowed_origins(monkeypatch):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "https://one, https://two")

    settings = server._resolve_transport_security("0.0.0.0")
    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == []
    assert settings.allowed_origins == ["https://one", "https://two"]


def test_transport_security_settings_hosts_and_origins(monkeypatch):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "host1")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "https://one")

    settings = server._resolve_transport_security("0.0.0.0")
    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["host1"]
    assert settings.allowed_origins == ["https://one"]


def test_resolve_transport_security_env_vars_override_localhost(monkeypatch):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "custom.example.com")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "")

    settings = server._resolve_transport_security("127.0.0.1")

    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["custom.example.com"]
    assert settings.allowed_origins == []


def test_non_localhost_host_header_not_rejected_when_env_vars_empty(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("BLOCKSCOUT_MCP_ALLOWED_ORIGINS", raising=False)

    from blockscout_mcp_server import server

    importlib.reload(server)
    try:
        server.mcp.settings.stateless_http = True
        server.mcp.settings.json_response = True
        server.mcp.settings.transport_security = server._resolve_transport_security("0.0.0.0")

        app = server.mcp.streamable_http_app()
        with TestClient(app) as client:
            response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                headers={"host": "staging.example.com"},
            )

        assert response.status_code != 421, "Got 421 Misdirected Request for non-localhost host"
        assert response.status_code < 500, f"Unexpected server error: {response.status_code}"
    finally:
        importlib.reload(server)


@pytest.mark.asyncio
async def test_all_registered_tools_have_output_schema():
    from blockscout_mcp_server import server

    for tool in await server.mcp.list_tools():
        assert tool.outputSchema is not None


@pytest.mark.asyncio
async def test_all_registered_tools_have_openai_invocation_status_meta():
    from blockscout_mcp_server import server

    tools = await server.mcp.list_tools()
    tools_with_statuses = 0

    for tool in tools:
        assert tool.meta is not None

        invoking = tool.meta.get("openai/toolInvocation/invoking")
        invoked = tool.meta.get("openai/toolInvocation/invoked")

        assert isinstance(invoking, str)
        assert invoking
        assert isinstance(invoked, str)
        assert invoked

        tools_with_statuses += 1

    assert tools_with_statuses == len(tools)


@pytest.mark.asyncio
async def test_all_registered_tools_have_expected_titles():
    from blockscout_mcp_server import server

    expected_titles_by_tool_name = {
        "__unlock_blockchain_analysis__": "Unlock Blockchain Analysis",
        "get_block_info": "Get Block Information",
        "get_block_number": "Get Block Number",
        "get_address_by_ens_name": "Get Address by ENS Name",
        "get_transactions_by_address": "Get Transactions by Address",
        "get_token_transfers_by_address": "Get Token Transfers by Address",
        "lookup_token_by_symbol": "Lookup Token by Symbol",
        "get_contract_abi": "Get Contract ABI",
        "inspect_contract_code": "Inspect Contract Code",
        "read_contract": "Read from Contract",
        "get_address_info": "Get Address Information",
        "get_tokens_by_address": "Get Tokens by Address",
        "nft_tokens_by_address": "Get NFT Tokens by Address",
        "get_transaction_info": "Get Transaction Information",
        "get_chains_list": "Get List of Chains",
        "direct_api_call": "Direct Blockscout API Call",
    }

    tools = await server.mcp.list_tools()

    assert len(tools) == len(expected_titles_by_tool_name)
    for tool in tools:
        assert tool.title == expected_titles_by_tool_name[tool.name]


@pytest.mark.asyncio
async def test_all_registered_tools_have_unique_titles():
    from blockscout_mcp_server import server

    tools = await server.mcp.list_tools()
    titles = [tool.title for tool in tools]

    assert len(set(titles)) == len(titles)


@pytest.mark.asyncio
async def test_all_registered_tools_have_behavioral_annotations_without_annotation_title():
    from blockscout_mcp_server import server

    for tool in await server.mcp.list_tools():
        assert tool.annotations is not None
        assert tool.annotations.title is None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.openWorldHint is True
