"""Centralized Mixpanel analytics for MCP tool invocations.

Tracking is enabled only when:
- BLOCKSCOUT_MIXPANEL_TOKEN is set, and
- server runs in HTTP mode (set via set_http_mode(True)).

Events are emitted via Mixpanel with a deterministic distinct_id based on a
connection fingerprint composed of client IP, client name, and client version.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

try:
    # Import lazily; tests will mock this
    from mixpanel import Consumer, Mixpanel
except ImportError:  # pragma: no cover

    class _MissingMixpanel:  # noqa: D401 - simple placeholder
        """Placeholder that raises if Mixpanel is actually used."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 - simple placeholder
            raise ImportError("Mixpanel library is not installed. Please install 'mixpanel' to use analytics features.")

    Consumer = _MissingMixpanel  # type: ignore[assignment]
    Mixpanel = _MissingMixpanel  # type: ignore[assignment]

from blockscout_mcp_server.client_meta import (
    ClientMeta,
    extract_client_meta_from_ctx,
    get_header_case_insensitive,
)
from blockscout_mcp_server.config import config

logger = logging.getLogger(__name__)


_is_http_mode_enabled: bool = False
_mp_client: Any | None = None


def set_http_mode(is_http: bool) -> None:
    """Enable or disable HTTP mode for analytics gating."""
    global _is_http_mode_enabled
    _is_http_mode_enabled = bool(is_http)
    # Log enablement status once at startup (HTTP path only)
    if _is_http_mode_enabled:
        token = getattr(config, "mixpanel_token", "")
        if token:
            # Best-effort initialize client to validate configuration
            _ = _get_mixpanel_client()
            api_host = getattr(config, "mixpanel_api_host", "") or "default"
            logger.info("Mixpanel analytics enabled (api_host=%s)", api_host)
        else:
            logger.debug("Mixpanel analytics not enabled: BLOCKSCOUT_MIXPANEL_TOKEN is not set")


def _get_mixpanel_client() -> Any | None:
    """Return a singleton Mixpanel client if token is configured."""
    global _mp_client
    if _mp_client is not None:
        return _mp_client
    token = getattr(config, "mixpanel_token", "")
    if not token:
        return None
    try:
        api_host = getattr(config, "mixpanel_api_host", "")
        if api_host:
            consumer = Consumer(api_host=api_host)
            _mp_client = Mixpanel(token, consumer=consumer)
        else:
            _mp_client = Mixpanel(token)
        return _mp_client
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to initialize Mixpanel client: %s", exc)
        return None


def _extract_request_ip(ctx: Any) -> str:
    """Extract client IP address from context if possible."""
    ip = ""
    try:
        request = getattr(getattr(ctx, "request_context", None), "request", None)
        if request is not None:
            headers = request.headers or {}
            # Prefer proxy-forwarded headers
            xff = get_header_case_insensitive(headers, "x-forwarded-for", "") or ""
            if xff:
                # left-most IP per standard
                ip = xff.split(",")[0].strip()
            else:
                x_real_ip = get_header_case_insensitive(headers, "x-real-ip", "") or ""
                if x_real_ip:
                    ip = x_real_ip
                else:
                    client = getattr(request, "client", None)
                    if client and getattr(client, "host", None):
                        ip = client.host
    except Exception:  # pragma: no cover - tolerate all shapes
        pass
    return ip


def _build_distinct_id(ip: str, client_name: str, client_version: str) -> str:
    # User-Agent is merged into client_name in extract_client_meta_from_ctx when name is unavailable.
    # Therefore composite requires only ip, client_name and client_version for a stable fingerprint.
    composite = "|".join([ip or "", client_name or "", client_version or ""])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://blockscout.com/mcp/" + composite))


def _determine_call_source(ctx: Any) -> str:
    """Return 'mcp' for MCP calls, 'rest' for REST API, else 'unknown'.

    Priority:
    1) Explicit marker set by caller (e.g., REST mock context) via `call_source`.
    2) Default to 'mcp' when no explicit marker is present (applies to MCP-over-HTTP).
    """
    try:
        explicit = getattr(ctx, "call_source", None)
        if isinstance(explicit, str) and explicit:
            return explicit
        # No explicit marker: treat as MCP (covers MCP-over-HTTP)
        return "mcp"
    except Exception:  # pragma: no cover
        pass
    return "unknown"


def track_tool_invocation(
    ctx: Any,
    tool_name: str,
    tool_args: dict[str, Any],
    client_meta: ClientMeta | None = None,
) -> None:
    """Track a tool invocation in Mixpanel, if enabled and in HTTP mode."""
    if not _is_http_mode_enabled:
        return
    mp = _get_mixpanel_client()
    if mp is None:
        return

    try:
        ip = _extract_request_ip(ctx)

        # Prefer provided client metadata from the decorator; otherwise, fall back to context
        if client_meta is not None:
            client_name = client_meta.name
            client_version = client_meta.version
            protocol_version = client_meta.protocol
            user_agent = client_meta.user_agent
        else:
            meta = extract_client_meta_from_ctx(ctx)
            client_name = meta.name
            client_version = meta.version
            protocol_version = meta.protocol
            user_agent = meta.user_agent

        distinct_id = _build_distinct_id(ip, client_name, client_version)

        properties: dict[str, Any] = {
            "ip": ip,
            "client_name": client_name,
            "client_version": client_version,
            "user_agent": user_agent,
            "tool_args": tool_args,
            "protocol_version": protocol_version,
            "source": _determine_call_source(ctx),
        }

        # TODO: Remove this log after validating Mixpanel analytics end-to-end
        logger.info(
            "Mixpanel event prepared: distinct_id=%s tool=%s properties=%s",
            distinct_id,
            tool_name,
            properties,
        )

        meta = {"ip": ip} if ip else None
        # Mixpanel Python SDK allows meta for IP geolocation mapping
        if meta is not None:
            mp.track(distinct_id, tool_name, properties, meta=meta)  # type: ignore[call-arg]
        else:
            mp.track(distinct_id, tool_name, properties)
    except Exception as exc:  # pragma: no cover - do not break tool flow
        logger.debug("Mixpanel tracking failed for %s: %s", tool_name, exc)
