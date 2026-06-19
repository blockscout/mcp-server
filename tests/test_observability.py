# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for blockscout_mcp_server.observability.log_resource_read."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import AnyUrl

from blockscout_mcp_server.client_meta import (
    UNDEFINED_CLIENT_NAME,
    UNDEFINED_CLIENT_VERSION,
    UNKNOWN_PROTOCOL_VERSION,
    ClientMeta,
    format_client_meta_suffix,
)
from blockscout_mcp_server.observability import log_resource_read

_SKILL_URI = "blockscout-mcp://skill/SKILL.md"
_LOGGER_NAME = "blockscout_mcp_server.observability"


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.session = None
    ctx.request_context = None
    return ctx


# ---------------------------------------------------------------------------
# Log format
# ---------------------------------------------------------------------------


def test_log_format_emits_info_with_label_and_suffix(caplog):
    """An INFO record contains 'Resource read: skill/SKILL.md' and the client suffix."""
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    ctx = _make_ctx()

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read"),
        patch("blockscout_mcp_server.observability.telemetry.send_community_resource_report", new_callable=AsyncMock),
        patch("blockscout_mcp_server.observability.asyncio.create_task"),
    ):
        log_resource_read(_SKILL_URI, ctx)

    records = [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.INFO]
    assert records, "Expected at least one INFO record from the observability logger"
    msg = records[0].getMessage()
    assert "Resource read: skill/SKILL.md" in msg
    # When ctx has no session/request, suffix is the N/A defaults.
    expected_suffix = format_client_meta_suffix(
        ClientMeta(UNDEFINED_CLIENT_NAME, UNDEFINED_CLIENT_VERSION, UNKNOWN_PROTOCOL_VERSION, "", {})
    )
    assert expected_suffix in msg


# ---------------------------------------------------------------------------
# URI normalisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uri_normalisation_anyurl_becomes_str():
    """AnyUrl passed to log_resource_read is normalised to a plain str for the sinks."""
    any_url = AnyUrl(_SKILL_URI)
    ctx = _make_ctx()
    captured: list[str] = []

    def fake_track(ctx_, uri_, client_meta=None):
        captured.append(uri_)

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read", side_effect=fake_track),
        patch("blockscout_mcp_server.observability.asyncio.create_task"),
    ):
        log_resource_read(any_url, ctx)

    assert captured, "track_resource_read was not called"
    assert isinstance(captured[0], str), "URI forwarded to analytics must be a plain str"
    assert captured[0] == _SKILL_URI


# ---------------------------------------------------------------------------
# Fan-out: both sinks are invoked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fan_out_both_sinks_called():
    """Both analytics.track_resource_read and telemetry.send_community_resource_report are invoked."""
    ctx = _make_ctx()

    mock_community = AsyncMock()

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read") as mock_track,
        patch(
            "blockscout_mcp_server.observability.telemetry.send_community_resource_report",
            return_value=mock_community(),
        ),
        patch("blockscout_mcp_server.observability.asyncio.create_task") as mock_create_task,
    ):
        log_resource_read(_SKILL_URI, ctx)
        # Drain tasks
        await asyncio.sleep(0)

    mock_track.assert_called_once()
    call_args = mock_track.call_args
    forwarded_uri = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("uri")
    assert forwarded_uri == _SKILL_URI
    mock_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# Error swallowing — no exception propagates
# ---------------------------------------------------------------------------


def test_no_exception_propagates_when_extract_meta_raises(monkeypatch):
    """log_resource_read does not propagate when extract_client_meta_from_ctx raises."""
    monkeypatch.setattr(
        "blockscout_mcp_server.observability.extract_client_meta_from_ctx",
        lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    ctx = _make_ctx()
    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read"),
        patch("blockscout_mcp_server.observability.asyncio.create_task"),
    ):
        log_resource_read(_SKILL_URI, ctx)  # must not raise


def test_no_exception_propagates_when_analytics_raises(monkeypatch):
    """log_resource_read does not propagate when track_resource_read raises."""
    monkeypatch.setattr(
        "blockscout_mcp_server.observability.analytics.track_resource_read",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("analytics boom")),
    )
    ctx = _make_ctx()
    with patch("blockscout_mcp_server.observability.asyncio.create_task"):
        log_resource_read(_SKILL_URI, ctx)  # must not raise


# ---------------------------------------------------------------------------
# Failure isolation across sinks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analytics_failure_does_not_suppress_community_report(caplog):
    """When analytics.track_resource_read raises, the community-telemetry sink is still scheduled."""
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    ctx = _make_ctx()

    def exploding_track(*args, **kwargs):
        raise RuntimeError("analytics exploded")

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read", side_effect=exploding_track),
        patch("blockscout_mcp_server.observability.asyncio.create_task") as mock_create_task,
    ):
        log_resource_read(_SKILL_URI, ctx)
        await asyncio.sleep(0)

    mock_create_task.assert_called_once()
    # Log line must still have been emitted
    records = [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.INFO]
    assert any("Resource read:" in r.getMessage() for r in records)


@pytest.mark.asyncio
async def test_community_failure_does_not_suppress_analytics(caplog):
    """When create_task (community telemetry) raises, analytics and log line are still produced."""
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    ctx = _make_ctx()

    def exploding_create_task(*args, **kwargs):
        raise RuntimeError("create_task exploded")

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read") as mock_track,
        patch("blockscout_mcp_server.observability.asyncio.create_task", side_effect=exploding_create_task),
    ):
        log_resource_read(_SKILL_URI, ctx)
        await asyncio.sleep(0)

    mock_track.assert_called_once()
    records = [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.INFO]
    assert any("Resource read:" in r.getMessage() for r in records)


# ---------------------------------------------------------------------------
# Metadata-extraction fallback: sentinel metadata, both sinks still attempted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metadata_extraction_failure_still_observes_read(caplog, monkeypatch):
    """When extract_client_meta_from_ctx raises, log line + both sinks are still attempted."""
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)

    def raising_extractor(ctx):
        raise RuntimeError("extractor failure")

    monkeypatch.setattr("blockscout_mcp_server.observability.extract_client_meta_from_ctx", raising_extractor)
    ctx = _make_ctx()

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read") as mock_track,
        patch("blockscout_mcp_server.observability.asyncio.create_task") as mock_create_task,
    ):
        log_resource_read(_SKILL_URI, ctx)
        await asyncio.sleep(0)

    # Log line must be emitted
    records = [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.INFO]
    assert any("Resource read:" in r.getMessage() for r in records), (
        "Log line must be emitted even on extractor failure"
    )

    # Both sinks must be attempted
    mock_track.assert_called_once()
    mock_create_task.assert_called_once()

    # Sinks should receive the sentinel metadata
    call_args = mock_track.call_args
    meta_arg = call_args.kwargs.get("client_meta") or (call_args.args[2] if len(call_args.args) > 2 else None)
    assert meta_arg is not None
    assert meta_arg.name == UNDEFINED_CLIENT_NAME
    assert meta_arg.version == UNDEFINED_CLIENT_VERSION
    assert meta_arg.protocol == UNKNOWN_PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Log-preparation/emission isolation: log block failure still leaves both sinks attempted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_block_failure_still_attempts_both_sinks(monkeypatch):
    """When uri_to_relative_path raises (inside the log block), both sinks are still attempted."""
    monkeypatch.setattr(
        "blockscout_mcp_server.observability.skill_resources.uri_to_relative_path",
        lambda uri: (_ for _ in ()).throw(RuntimeError("path resolution failure")),
    )
    ctx = _make_ctx()

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read") as mock_track,
        patch("blockscout_mcp_server.observability.asyncio.create_task") as mock_create_task,
    ):
        log_resource_read(_SKILL_URI, ctx)
        await asyncio.sleep(0)

    mock_track.assert_called_once()
    call_args = mock_track.call_args
    # Full URI string must be forwarded, not a label-relative form
    assert call_args.args[1] == _SKILL_URI or call_args.kwargs.get("uri") == _SKILL_URI
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_format_suffix_failure_still_attempts_both_sinks(monkeypatch):
    """When format_client_meta_suffix raises, both sinks are still attempted."""
    monkeypatch.setattr(
        "blockscout_mcp_server.observability.format_client_meta_suffix",
        lambda meta: (_ for _ in ()).throw(RuntimeError("format failure")),
    )
    ctx = _make_ctx()

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read") as mock_track,
        patch("blockscout_mcp_server.observability.asyncio.create_task") as mock_create_task,
    ):
        log_resource_read(_SKILL_URI, ctx)
        await asyncio.sleep(0)

    mock_track.assert_called_once()
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_logger_info_failure_still_attempts_both_sinks(monkeypatch):
    """When logger.info raises, both sinks are still attempted."""
    monkeypatch.setattr(
        "blockscout_mcp_server.observability.logger",
        MagicMock(info=MagicMock(side_effect=RuntimeError("logger failure"))),
    )
    ctx = _make_ctx()

    with (
        patch("blockscout_mcp_server.observability.analytics.track_resource_read") as mock_track,
        patch("blockscout_mcp_server.observability.asyncio.create_task") as mock_create_task,
    ):
        log_resource_read(_SKILL_URI, ctx)
        await asyncio.sleep(0)

    mock_track.assert_called_once()
    call_args = mock_track.call_args
    assert call_args.args[1] == _SKILL_URI
    mock_create_task.assert_called_once()
