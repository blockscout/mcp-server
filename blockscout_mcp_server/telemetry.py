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


def is_any_telemetry_active() -> bool:
    """Return whether any telemetry sink can still emit under the current config.

    Single source of truth for the "is it worth deriving the request's auth
    identity at all?" precondition, replacing the inline boolean that used to
    duplicate the analytics and community sinks' own gates at each derivation site.
    Kept deliberately coarse and conservative: it is a *superset* of the union of
    the two sinks' precise send conditions, so it reports *inactive* only when
    telemetry is provably off (not HTTP mode **and** community telemetry disabled).
    Erring toward "active" keeps callers independent of each sink's internal logic;
    the sinks still self-gate before actually sending.
    """
    return analytics.is_http_mode_enabled() or not config.disable_community_telemetry


def resolve_auth_signals(ctx: Any) -> tuple[AuthOrigin | None, str | None]:
    """Derive the ``(auth_origin, api_key_fingerprint)`` pair for the observability sinks.

    Single entry point shared by both observability paths — ``log_tool_invocation``
    (the tool decorator) and ``log_resource_read`` — so the one ``ctx`` extraction
    and SHA-256 (in :func:`compute_auth_signals`), the defensive guard, and the
    all-telemetry-disabled short-circuit are written once instead of duplicated at
    each site. Returns ``(None, None)`` without touching ``ctx`` when no sink can
    consume the signals (see :func:`is_any_telemetry_active`); both sinks
    short-circuit on their own gates in that state anyway, so nothing emitted
    changes while the ``ctx`` extraction and key hashing are skipped.

    The fingerprint is forward-provisioned: today only the community usage report
    consumes it, but it is intended to key Mixpanel ``distinct_id`` per
    user/instance depending on deployment (see SPEC.md -> Performance Optimizations
    -> Dual-Mode Analytics). That is why signals are derived whenever *any*
    telemetry sink is active, not only when community telemetry is enabled.

    Never raises: :func:`compute_auth_signals` is defensive today, and the gate is
    evaluated *inside* the ``try`` so this observability concern can never propagate
    into the tool body even if either contract later changes. The ``(None, None)``
    fallback degrades gracefully — the analytics sink records the origin as
    ``AUTH_ORIGIN_UNKNOWN`` (it never re-derives from ``ctx``), the community report
    omits the hash.
    """
    try:
        if not is_any_telemetry_active():
            return None, None
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
