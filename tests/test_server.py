import importlib
import json
import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient
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


def test_resolve_transport_security_localhost_no_env_vars(monkeypatch):
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.config, "mcp_allowed_hosts", "")
    monkeypatch.setattr(server.config, "mcp_allowed_origins", "")

    settings = server._resolve_transport_security("127.0.0.1")

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

        assert response.status_code != 421
    finally:
        importlib.reload(server)


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_with_content_text():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool() -> ToolResponse[dict]:
        """doc"""
        return ToolResponse(data={"a": 1}, content_text="hello")

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped()

    expected_structured = {
        "data": {"a": 1},
        "data_description": None,
        "notes": None,
        "instructions": None,
        "pagination": None,
    }
    assert json.loads(result.content[0].text) == expected_structured
    assert result.structuredContent == expected_structured


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_fallback_and_metadata():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool() -> ToolResponse[dict]:
        """wrapped doc"""
        return ToolResponse(data={"a": 1})

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped()

    assert json.loads(result.content[0].text) == result.structuredContent
    assert "content_text" not in result.structuredContent
    assert wrapped.__name__ == _tool.__name__
    assert wrapped.__doc__ == _tool.__doc__
    assert wrapped.__annotations__ == _tool.__annotations__


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_openai_client_uses_summary_content():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1}, content_text="hello")

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"openai/userAgent": "ChatGPT/1.0"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert result.content[0].text == "hello"
    assert result.structuredContent["data"] == {"a": 1}


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_non_openai_client_uses_json_content():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1}, content_text="hello")

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"someOther/field": "value"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_non_openai_client_preserves_unicode_in_json_content():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"label": "привіт 👋"}, content_text="hello")

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"someOther/field": "value"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert "привіт" in result.content[0].text
    assert "\\u043f" not in result.content[0].text
    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_openai_client_without_content_text_uses_fallback():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1})

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"openai/userAgent": "ChatGPT/1.0"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert result.content[0].text == "Tool executed successfully."


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_structured_content_same_for_all_clients():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1}, content_text="hello")

    openai_ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"openai/userAgent": "ChatGPT/1.0"}, request=SimpleNamespace(headers={})),
    )
    other_ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"someOther/field": "value"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    openai_result = await wrapped(ctx=openai_ctx)
    other_result = await wrapped(ctx=other_ctx)

    assert openai_result.structuredContent == other_result.structuredContent


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
