# SPDX-License-Identifier: LicenseRef-Blockscout
import logging

import httpx

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    COMMUNITY_TELEMETRY_ENDPOINT,
    COMMUNITY_TELEMETRY_URL,
    RESOURCE_READ_EVENT,
    SERVER_VERSION,
)

logger = logging.getLogger(__name__)


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
