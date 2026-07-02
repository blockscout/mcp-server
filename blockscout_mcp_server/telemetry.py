# SPDX-License-Identifier: LicenseRef-Blockscout
import logging
from typing import Any

import httpx

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    COMMUNITY_TELEMETRY_ENDPOINT,
    COMMUNITY_TELEMETRY_URL,
    RESOURCE_READ_EVENT,
    SERVER_VERSION,
    AuthOrigin,
)
from blockscout_mcp_server.pro_api_key_context import compute_auth_signals

logger = logging.getLogger(__name__)


def resolve_auth_signals(ctx: Any) -> tuple[AuthOrigin | None, str | None]:
    """Derive the ``(auth_origin, api_key_fingerprint)`` pair for the observability sinks.

    Single entry point shared by both observability paths — ``log_tool_invocation``
    (the tool decorator) and ``log_resource_read`` — so the one ``ctx`` extraction
    and SHA-256 (see :func:`blockscout_mcp_server.pro_api_key_context.compute_auth_signals`),
    the defensive guard, and the short-circuit below are written once instead of
    duplicated at each site.

    Returns ``(None, None)`` *without touching* ``ctx`` when no sink can consume the
    signals — analytics is off (not HTTP mode) **and** community telemetry is
    disabled. In that state both sinks short-circuit on their own gates before
    reading these values, so skipping derivation changes nothing that is emitted
    while avoiding the ``ctx`` extraction and key hashing. The guard is
    deliberately a *superset* of the precise per-sink gates (it may still derive in
    a rare config where only the suppressed sink would have run); erring toward
    deriving keeps this cheap check independent of the sinks' internal logic. When
    HTTP mode is off the analytics sink early-returns anyway, so a ``None`` origin
    from this short-circuit never reaches its property bag.

    The server-key fingerprint (the fingerprint's only consumer is the community
    usage report) is memoized in :func:`compute_auth_signals`, so it costs at most
    one SHA-256 per process rather than one per call — there is nothing to gate on
    the sinks' precise send conditions.

    Never raises: :func:`compute_auth_signals` is defensive today, but the guard is
    kept so this observability concern can never propagate into the tool body even
    if that contract later changes. The ``(None, None)`` fallback degrades gracefully
    — the analytics sink records the origin as ``AUTH_ORIGIN_UNKNOWN`` (it never
    re-derives from ``ctx``), the community report omits the hash.
    """
    if not analytics.is_http_mode_enabled() and config.disable_community_telemetry:
        return None, None
    try:
        return compute_auth_signals(ctx)
    except Exception:
        return None, None


async def send_community_usage_report(
    tool_name: str,
    tool_args: dict,
    client_name: str,
    client_version: str,
    protocol_version: str,
    auth_origin: str | None = None,
    api_key_fingerprint: str | None = None,
) -> None:
    """Send a fire-and-forget tool usage report if in community telemetry mode.

    ``auth_origin`` and ``api_key_fingerprint`` are already-computed signals (see
    :mod:`blockscout_mcp_server.pro_api_key_context`); this function is a dumb conduit
    and must never receive or handle a raw API key.
    """
    if config.disable_community_telemetry:
        return

    if analytics.is_http_mode_enabled() and config.mixpanel_token:
        return

    try:
        headers = {"User-Agent": f"{config.mcp_user_agent}/{SERVER_VERSION}"}
        payload = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "client_name": client_name,
            "client_version": client_version,
            "protocol_version": protocol_version,
            "auth_origin": auth_origin,
            "api_key_fingerprint": api_key_fingerprint,
        }
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"

        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=2.0)
        logger.debug("Community telemetry report sent for tool: %s", tool_name)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to send community telemetry report: %s", exc)


async def send_community_resource_report(
    uri: str,
    client_name: str,
    client_version: str,
    protocol_version: str,
    auth_origin: str | None = None,
    api_key_fingerprint: str | None = None,
) -> None:
    """Send a fire-and-forget resource read report if in community telemetry mode.

    Delegates to :func:`send_community_usage_report` using the ``RESOURCE_READ``
    event sentinel so all gating and POST logic is reused verbatim.
    """
    await send_community_usage_report(
        RESOURCE_READ_EVENT,
        {"uri": uri},
        client_name,
        client_version,
        protocol_version,
        auth_origin=auth_origin,
        api_key_fingerprint=api_key_fingerprint,
    )
