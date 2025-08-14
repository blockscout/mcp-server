import types
from unittest.mock import MagicMock, patch

import pytest

from blockscout_mcp_server import analytics
from blockscout_mcp_server.analytics import ClientMeta
from blockscout_mcp_server.config import config as server_config


class DummyRequest:
    def __init__(self, headers=None, host="127.0.0.1"):
        self.headers = headers or {}
        self.client = types.SimpleNamespace(host=host)


class DummyCtx:
    def __init__(self, request=None, client_name="", client_version=""):
        self.request_context = types.SimpleNamespace(request=request) if request else None
        clientInfo = types.SimpleNamespace(name=client_name, version=client_version)
        self.session = types.SimpleNamespace(client_params=types.SimpleNamespace(clientInfo=clientInfo))


@pytest.fixture(autouse=True)
def reset_mode_and_client(monkeypatch):
    analytics.set_http_mode(False)
    # Ensure private module state is reset between tests
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)  # type: ignore[attr-defined]
    yield
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)  # type: ignore[attr-defined]


def test_noop_when_not_http_mode(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        analytics.track_tool_invocation(DummyCtx(), "some_tool", {"a": 1})
        mp_cls.assert_not_called()


def test_noop_when_no_token(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "", raising=False)
    analytics.set_http_mode(True)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        analytics.track_tool_invocation(DummyCtx(), "some_tool", {"a": 1})
        mp_cls.assert_not_called()


def test_tracks_with_headers(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {"x-forwarded-for": "203.0.113.5, 70.41.3.18", "user-agent": "pytest-UA"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(
            ctx,
            "tool_name",
            {"x": 2},
            client_meta=ClientMeta(name="clientA", version="1.0.0", protocol="2024-11-05", user_agent="pytest-UA"),
        )
        assert mp_instance.track.called
        args, kwargs = mp_instance.track.call_args
        # distinct_id, event, properties
        assert args[1] == "tool_name"
        assert args[2]["ip"] == "203.0.113.5"
        assert args[2]["client_name"] == "clientA"
        assert args[2]["client_version"] == "1.0.0"
        assert args[2]["user_agent"] == "pytest-UA"
        assert args[2]["tool_args"] == {"x": 2}
        assert args[2]["protocol_version"] == "2024-11-05"
        assert kwargs.get("meta") == {"ip": "203.0.113.5"}


def test_tracks_with_intermediary_header(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {
        "x-forwarded-for": "203.0.113.5",
        "user-agent": "pytest-UA",
        "Blockscout-MCP-Intermediary": "ClaudeDesktop",
    }
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="node", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "tool_name", {"x": 2})
        args, _ = mp_instance.track.call_args
        assert args[2]["client_name"] == "node/ClaudeDesktop"


def test_tracks_with_invalid_intermediary(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {
        "x-forwarded-for": "203.0.113.5",
        "user-agent": "pytest-UA",
        "Blockscout-MCP-Intermediary": "Unknown",
    }
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="node", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "tool_name", {"x": 2})
        args, _ = mp_instance.track.call_args
        assert args[2]["client_name"] == "node"


def test_tracks_with_intermediary_and_user_agent_fallback(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {
        "x-forwarded-for": "203.0.113.5",
        "user-agent": "pytest-UA",
        "Blockscout-MCP-Intermediary": "HigressPlugin",
    }
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="", client_version="")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "tool_name", {"x": 2})
        args, _ = mp_instance.track.call_args
        assert args[2]["client_name"] == "pytest-UA/HigressPlugin"


def test_tracks_with_intermediary_no_client_or_user_agent(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {"Blockscout-MCP-Intermediary": "ClaudeDesktop"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="", client_version="")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "tool_name", {"x": 2})
        args, _ = mp_instance.track.call_args
        assert args[2]["client_name"] == "N/A/ClaudeDesktop"
