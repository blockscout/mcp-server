import logging

import httpx

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    COMMUNITY_TELEMETRY_ENDPOINT,
    COMMUNITY_TELEMETRY_URL,
    SERVER_VERSION,
)

logger = logging.getLogger(__name__)


async def send_community_usage_report(tool_name: str, tool_args: dict) -> None:
    """Send a fire-and-forget tool usage report if in community telemetry mode."""
    if config.disable_community_telemetry:
        return

    if analytics._is_http_mode_enabled and config.mixpanel_token:
        return

    try:
        headers = {"User-Agent": f"{config.mcp_user_agent}/{SERVER_VERSION}"}
        payload = {"tool_name": tool_name, "tool_args": tool_args}
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"

        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=2.0)
        logger.debug("Community telemetry report sent for tool: %s", tool_name)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to send community telemetry report: %s", exc)
