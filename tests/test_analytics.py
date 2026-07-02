# SPDX-License-Identifier: LicenseRef-Blockscout
import types
from unittest.mock import MagicMock, patch

import pytest

from blockscout_mcp_server import analytics
from blockscout_mcp_server.analytics import ClientMeta
from blockscout_mcp_server.config import config as server_config
from blockscout_mcp_server.constants import RESOURCE_READ_EVENT
from blockscout_mcp_server.models import ToolUsageReport


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


def test_tracks_threaded_auth_origin_into_property_bag(monkeypatch):
    """The pre-computed ``auth_origin`` threaded by the caller reaches the property bag verbatim."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {"x-forwarded-for": "203.0.113.5", "user-agent": "pytest-UA"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "tool_name", {"x": 2}, auth_origin="server")
        args, _ = mp_instance.track.call_args
        assert args[2]["auth_origin"] == "server"


def test_tracks_auth_origin_unknown_when_not_threaded(monkeypatch):
    """When no ``auth_origin`` is threaded (``None``), the sink records the ``unknown`` sentinel.

    The sink never re-derives the origin from ``ctx`` — doing so would re-run the
    computation that ``telemetry.resolve_auth_signals`` already guarded and, if it
    fails, drop the whole Mixpanel event. Mirrors ``track_community_usage``.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "server-secret", raising=False)
    headers = {"x-forwarded-for": "203.0.113.5", "user-agent": "pytest-UA"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "tool_name", {"x": 2})
        args, _ = mp_instance.track.call_args
        assert args[2]["auth_origin"] == "unknown"


def test_track_event_tracks_when_enabled(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    req = DummyRequest(headers={"user-agent": "pytest-UA"}, host="203.0.113.5")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_event(req, "PageView", {"path": "/"})
        mp_instance.track.assert_called_once()
        args, kwargs = mp_instance.track.call_args
        assert args[1] == "PageView"
        assert args[2]["ip"] == "203.0.113.5"
        assert args[2]["user_agent"] == "pytest-UA"
        assert args[2]["path"] == "/"
        assert kwargs.get("meta") == {"ip": "203.0.113.5"}


def test_track_event_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "", raising=False)
    analytics.set_http_mode(True)
    req = DummyRequest()
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        analytics.track_event(req, "PageView", {"path": "/"})
        mp_cls.assert_not_called()


def test_pro_api_key_not_in_analytics_payload(monkeypatch):
    """The client-supplied PRO API key must not appear in the Mixpanel payload or kwargs.

    analytics.track_tool_invocation runs inside log_tool_invocation, which executes
    *outside* the pro_api_key_scope. Even so, this test exercises the case where the
    context object carries the configured header to ensure no code path leaks it.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)

    client_key = "client-secret"
    headers = {
        "x-forwarded-for": "203.0.113.5",
        "user-agent": "pytest-UA",
        "Blockscout-MCP-Pro-Api-Key": client_key,
    }
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="test-client", client_version="1.0.0")

    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "some_tool", {"x": 1}, auth_origin="client")

        assert mp_instance.track.called
        call_args = mp_instance.track.call_args

        # Inspect every string in the call for the key value and header name
        all_text = str(call_args)
        assert client_key not in all_text
        # Case-insensitive: catch a leaked header name regardless of casing.
        assert "blockscout-mcp-pro-api-key" not in all_text.lower()

        # Also explicitly check that the properties dict doesn't contain the key
        args, kwargs = call_args
        properties = args[2] if len(args) > 2 else {}
        assert client_key not in str(properties)
        assert client_key not in str(kwargs)

        # The caller threaded auth_origin='client'; it reaches the bag but the key never does.
        assert properties.get("auth_origin") == "client"
        assert "api_key_fingerprint" not in properties


def test_pro_api_key_not_in_analytics_payload_rest_source(monkeypatch):
    """The client-supplied PRO API key must not appear in the Mixpanel payload on the REST path.

    This test is a focused variant of test_pro_api_key_not_in_analytics_payload
    where the context is explicitly marked call_source = 'rest' — the path that
    now reads the REST header. Guards that reading the header on the REST source
    does not accidentally leak the key value or the header name into analytics,
    and that the reported source is 'rest'.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)

    client_key = "rest-client-secret"
    headers = {
        "x-forwarded-for": "203.0.113.5",
        "user-agent": "pytest-UA",
        "Blockscout-MCP-Pro-Api-Key": client_key,
    }
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="test-client", client_version="1.0.0")
    # Explicitly mark this context as coming from the REST path
    ctx.call_source = "rest"

    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "some_tool", {"x": 1}, auth_origin="client")

        assert mp_instance.track.called
        call_args = mp_instance.track.call_args

        # Inspect every string in the call for the key value and header name
        all_text = str(call_args)
        assert client_key not in all_text
        # Case-insensitive: catch a leaked header name regardless of casing.
        assert "blockscout-mcp-pro-api-key" not in all_text.lower()

        # Also explicitly check that the properties dict doesn't contain the key
        args, kwargs = call_args
        properties = args[2] if len(args) > 2 else {}
        assert client_key not in str(properties)
        assert client_key not in str(kwargs)

        # Confirm the source is correctly reported as 'rest'
        assert properties.get("source") == "rest"

        # The caller threaded auth_origin='client'; it reaches the bag but the key never does.
        assert properties.get("auth_origin") == "client"
        assert "api_key_fingerprint" not in properties


def test_track_community_usage(monkeypatch):
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        report = ToolUsageReport(
            tool_name="foo",
            tool_args={"a": 1},
            client_name="cli",
            client_version="1.0",
            protocol_version="1.1",
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        mp_instance.track.assert_called_once()
        args, kwargs = mp_instance.track.call_args
        assert args[1] == "foo"
        properties = args[2]
        assert properties["source"] == "community"
        assert properties["client_name"] == "cli"
        assert properties["client_version"] == "1.0"
        assert properties["protocol_version"] == "1.1"
        assert kwargs.get("meta") == {"ip": "203.0.113.5"}


def test_track_community_usage_auth_origin_from_report(monkeypatch):
    """auth_origin is forwarded verbatim from the report when present."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        report = ToolUsageReport(
            tool_name="foo",
            tool_args={"a": 1},
            client_name="cli",
            client_version="1.0",
            protocol_version="1.1",
            auth_origin="server",
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        args, _ = mp_instance.track.call_args
        properties = args[2]
        assert properties["auth_origin"] == "server"


def test_track_community_usage_auth_origin_defaults_to_unknown(monkeypatch):
    """A legacy report with no auth_origin maps to the 'unknown' sentinel."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        report = ToolUsageReport(
            tool_name="foo",
            tool_args={"a": 1},
            client_name="cli",
            client_version="1.0",
            protocol_version="1.1",
            auth_origin=None,
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        args, _ = mp_instance.track.call_args
        properties = args[2]
        assert properties["auth_origin"] == "unknown"


def test_track_community_usage_fingerprint_never_reaches_mixpanel(monkeypatch):
    """The api_key_fingerprint must not leak anywhere in the Mixpanel call.

    Checks the entire call (distinct_id, event name, properties, meta) for the
    fingerprint value, not merely the `properties["api_key_fingerprint"]` key
    -- this also catches a leak via distinct_id or a differently named property.
    Also asserts distinct_id is unaffected by the fingerprint (still derived
    only from ip/client_name/client_version), proving identity is not yet
    strengthened by it.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    distinctive_fingerprint = "ab" * 32  # 64-char lowercase hex, easy to spot in a leak
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        report = ToolUsageReport(
            tool_name="foo",
            tool_args={"a": 1},
            client_name="cli",
            client_version="1.0",
            protocol_version="1.1",
            auth_origin="client",
            api_key_fingerprint=distinctive_fingerprint,
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        mp_instance.track.assert_called_once()
        call_args = mp_instance.track.call_args
        assert distinctive_fingerprint not in str(call_args)

        args, _ = call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", report.client_name, report.client_version)
        assert args[0] == expected_distinct_id


# ---------------------------------------------------------------------------
# track_resource_read tests
# ---------------------------------------------------------------------------


def test_track_resource_read_noop_when_not_http_mode(monkeypatch):
    """No Mixpanel call when HTTP mode is disabled."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        analytics.track_resource_read(DummyCtx(), "blockscout-mcp://skill/SKILL.md")
        mp_cls.assert_not_called()


def test_track_resource_read_noop_when_no_token(monkeypatch):
    """No Mixpanel call when HTTP mode is on but no token is configured."""
    monkeypatch.setattr(server_config, "mixpanel_token", "", raising=False)
    analytics.set_http_mode(True)
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        analytics.track_resource_read(DummyCtx(), "blockscout-mcp://skill/SKILL.md")
        mp_cls.assert_not_called()


def test_track_resource_read_emits_correct_event(monkeypatch):
    """When enabled, mp.track is called with RESOURCE_READ event and uri in tool_args."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    uri = "blockscout-mcp://skill/SKILL.md"
    headers = {
        "x-forwarded-for": "203.0.113.5",
        "user-agent": "pytest-UA",
        "Blockscout-MCP-Pro-Api-Key": "client-secret",
    }
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_resource_read(
            ctx,
            uri,
            client_meta=ClientMeta(name="clientA", version="1.0.0", protocol="2024-11-05", user_agent="pytest-UA"),
            auth_origin="client",
        )
        mp_instance.track.assert_called_once()
        args, kwargs = mp_instance.track.call_args
        assert args[1] == RESOURCE_READ_EVENT
        properties = args[2]
        assert properties["tool_args"] == {"uri": uri}
        assert properties["client_name"] == "clientA"
        assert properties["client_version"] == "1.0.0"
        assert properties["protocol_version"] == "2024-11-05"
        assert properties["ip"] == "203.0.113.5"
        assert "source" in properties
        # track_resource_read threads the caller's auth_origin straight through to
        # track_tool_invocation, so the value provided here reaches the property bag.
        assert properties["auth_origin"] == "client"
