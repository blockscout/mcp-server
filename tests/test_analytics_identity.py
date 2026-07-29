# SPDX-License-Identifier: LicenseRef-Blockscout
"""Identity-basis tests for the community-reporting analytics path.

Kept in a dedicated module rather than tests/test_analytics.py because that file
sits exactly at the 500-LOC cap from rule 210.
"""

import types
from unittest.mock import MagicMock, patch

import pytest

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config as server_config
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


def test_track_community_usage_fingerprint_basis_with_client_origin(monkeypatch):
    """Report with fingerprint, auth_origin='client' -> distinct_id is the fingerprint basis."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "ab" * 32
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
            api_key_fingerprint=fingerprint,
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_fingerprint_distinct_id(fingerprint)
        assert args[0] == expected_distinct_id


def test_track_community_usage_fingerprint_basis_with_server_origin(monkeypatch):
    """Report with fingerprint, auth_origin='server' -> fingerprint basis (installation identity)."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "cd" * 32
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
            api_key_fingerprint=fingerprint,
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_fingerprint_distinct_id(fingerprint)
        assert args[0] == expected_distinct_id


def test_track_community_usage_fingerprint_basis_with_unknown_origin(monkeypatch):
    """Report with fingerprint, auth_origin=None -> fingerprint basis (pins "regardless of origin")."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "ef" * 32
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
            api_key_fingerprint=fingerprint,
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_fingerprint_distinct_id(fingerprint)
        assert args[0] == expected_distinct_id


def test_track_community_usage_legacy_basis_without_fingerprint(monkeypatch):
    """Report without a fingerprint -> legacy composite basis (legacy reporters keep being counted)."""
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
            auth_origin="client",
            api_key_fingerprint=None,
        )
        analytics.track_community_usage(report, ip="203.0.113.5", user_agent="ua")
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", report.client_name, report.client_version)
        assert args[0] == expected_distinct_id


def test_track_community_usage_fingerprint_never_reaches_mixpanel(monkeypatch):
    """The api_key_fingerprint must not leak anywhere in the Mixpanel call.

    Checks the entire call (distinct_id, event name, properties, meta) for the
    fingerprint value, not merely the `properties["api_key_fingerprint"]` key
    -- this also catches a leak via distinct_id or a differently named property.
    The UUIDv5 wrapping preserves the leak invariant even though the digest now
    keys the identity: distinct_id equals the fingerprint-based derivation, not
    the raw digest and not the legacy composite.
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
        expected_distinct_id = analytics._build_fingerprint_distinct_id(distinctive_fingerprint)
        assert args[0] == expected_distinct_id


# --- Direct-path (track_tool_invocation / track_resource_read) basis matrix ---


def test_track_tool_invocation_fingerprint_basis_with_client_origin(monkeypatch):
    """auth_origin='client' with a fingerprint -> distinct_id is the fingerprint basis.

    The fingerprint must not leak into `properties` under any key, nor appear
    anywhere in the raw call args.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "ab" * 32
    ctx = DummyCtx(client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(
            ctx, "some_tool", {"x": 1}, auth_origin="client", api_key_fingerprint=fingerprint
        )
        mp_instance.track.assert_called_once()
        call_args = mp_instance.track.call_args
        args, _ = call_args
        expected_distinct_id = analytics._build_fingerprint_distinct_id(fingerprint)
        assert args[0] == expected_distinct_id

        properties = args[2]
        assert "api_key_fingerprint" not in properties
        assert fingerprint not in str(call_args)


def test_track_tool_invocation_legacy_basis_when_client_origin_missing_fingerprint(monkeypatch):
    """auth_origin='client' with api_key_fingerprint=None -> legacy composite basis.

    This is the graceful-degradation row: the leak tests in test_analytics.py
    assert only non-leakage, not which basis is chosen, so it is pinned here.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {"x-forwarded-for": "203.0.113.5"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "some_tool", {"x": 1}, auth_origin="client", api_key_fingerprint=None)
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", "clientA", "1.0.0")
        assert args[0] == expected_distinct_id


def test_track_tool_invocation_legacy_basis_with_server_origin_and_fingerprint(monkeypatch):
    """auth_origin='server' with a fingerprint -> legacy basis (shared-key collapse prevention)."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "cd" * 32
    headers = {"x-forwarded-for": "203.0.113.5"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(
            ctx, "some_tool", {"x": 1}, auth_origin="server", api_key_fingerprint=fingerprint
        )
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", "clientA", "1.0.0")
        assert args[0] == expected_distinct_id
        assert fingerprint not in str(mp_instance.track.call_args)


@pytest.mark.parametrize("origin", ["none", None])
def test_track_tool_invocation_legacy_basis_with_no_client_origin(monkeypatch, origin):
    """auth_origin='none' or None, no fingerprint -> legacy basis."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    headers = {"x-forwarded-for": "203.0.113.5"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "some_tool", {"x": 1}, auth_origin=origin, api_key_fingerprint=None)
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", "clientA", "1.0.0")
        assert args[0] == expected_distinct_id


@pytest.mark.parametrize("origin", ["none", None])
def test_track_tool_invocation_legacy_basis_with_no_client_origin_and_fingerprint(monkeypatch, origin):
    """auth_origin='none' or None WITH a fingerprint -> legacy basis (defensive row).

    resolve_auth_signals never emits these combinations (each branch pairs origin and
    fingerprint atomically), but track_tool_invocation's docstring promises degradation to
    the legacy basis without relying on that caller contract, so it is pinned here.
    """
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "ab" * 32
    headers = {"x-forwarded-for": "203.0.113.5"}
    req = DummyRequest(headers=headers)
    ctx = DummyCtx(request=req, client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_tool_invocation(ctx, "some_tool", {"x": 1}, auth_origin=origin, api_key_fingerprint=fingerprint)
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", "clientA", "1.0.0")
        assert args[0] == expected_distinct_id
        assert fingerprint not in str(mp_instance.track.call_args)


def test_track_resource_read_forwards_fingerprint_unchanged(monkeypatch):
    """track_resource_read forwards api_key_fingerprint to track_tool_invocation unchanged."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    fingerprint = "ef" * 32
    ctx = DummyCtx(client_name="clientA", client_version="1.0.0")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_resource_read(
            ctx,
            "blockscout-mcp://skill/SKILL.md",
            auth_origin="client",
            api_key_fingerprint=fingerprint,
        )
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_fingerprint_distinct_id(fingerprint)
        assert args[0] == expected_distinct_id


def test_track_event_unchanged_ip_user_agent_basis(monkeypatch):
    """track_event (PageView path) still derives identity from ip/user-agent only."""
    monkeypatch.setattr(server_config, "mixpanel_token", "test-token", raising=False)
    req = DummyRequest(headers={"user-agent": "pytest-UA"}, host="203.0.113.5")
    with patch("blockscout_mcp_server.analytics.Mixpanel") as mp_cls:
        mp_instance = MagicMock()
        mp_cls.return_value = mp_instance
        analytics.set_http_mode(True)
        analytics.track_event(req, "PageView", {"path": "/"})
        args, _ = mp_instance.track.call_args
        expected_distinct_id = analytics._build_distinct_id("203.0.113.5", "pytest-UA", "N/A")
        assert args[0] == expected_distinct_id
