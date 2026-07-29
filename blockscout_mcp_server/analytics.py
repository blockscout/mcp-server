# SPDX-License-Identifier: LicenseRef-Blockscout
"""Centralized Mixpanel analytics for MCP tool invocations.

Tracking is enabled only when:
- BLOCKSCOUT_MIXPANEL_TOKEN is set, and
- server runs in HTTP mode (set via set_http_mode(True)).

Events are emitted via Mixpanel with a deterministic distinct_id derived from one
of two bases, selected per-path: the legacy composite of client IP, client name,
and client version, or the caller's PRO API key fingerprint. Which basis applies
depends on how the event reached analytics -- see `track_tool_invocation` and
`track_community_usage` for the exact selection rule on each path.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from starlette.requests import Request

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
from blockscout_mcp_server.constants import AUTH_ORIGIN_UNKNOWN, RESOURCE_READ_EVENT, AuthOrigin
from blockscout_mcp_server.models import ToolUsageReport

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


def is_http_mode_enabled() -> bool:
    """Check if HTTP mode is currently enabled."""
    return _is_http_mode_enabled


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


def _extract_ip_from_request(request: Request | None) -> str:
    """Extract a client IP address from a ``Request`` if possible."""
    ip = ""
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
    return ip


def _extract_request_ip(ctx: Any) -> str:
    """Extract client IP address from context if possible."""
    try:
        request = getattr(getattr(ctx, "request_context", None), "request", None)
        return _extract_ip_from_request(request)
    except Exception:  # pragma: no cover - tolerate all shapes
        return ""


def _build_distinct_id(ip: str, client_name: str, client_version: str) -> str:
    # User-Agent is merged into client_name in extract_client_meta_from_ctx when name is unavailable.
    # Therefore composite requires only ip, client_name and client_version for a stable fingerprint.
    composite = "|".join([ip or "", client_name or "", client_version or ""])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://mcp.blockscout.com/mcp" + composite))


def _build_fingerprint_distinct_id(fingerprint: str) -> str:
    # The two bases' input spaces are structurally disjoint: every input here is "key:" plus
    # 64 hex characters (a sha256 hexdigest on the direct path, validator-enforced shape on
    # the community path) and so contains no "|", while every legacy composite above contains
    # exactly two "|" separators. The "key:" tag is not what prevents the collision — a
    # composite CAN start with "key:", since its ip field is free text from a spoofable
    # header — it future-proofs the separation should the composite format ever change.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://mcp.blockscout.com/mcp" + "key:" + fingerprint))


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


def track_event(request: Request, event_name: str, properties: dict | None = None) -> None:
    """Track a generic event in Mixpanel using a Starlette ``Request``.

    Unlike :func:`track_tool_invocation`, this helper is intended for events that
    are not tied to a specific MCP tool. It extracts the client's IP address and
    ``User-Agent`` from the incoming HTTP ``Request`` and forwards the event to
    Mixpanel if analytics are enabled.

    Parameters
    ----------
    request:
        Incoming HTTP request used to extract client metadata.
    event_name:
        Name of the event to record.
    properties:
        Optional additional event properties to include in the Mixpanel payload.
    """
    if not _is_http_mode_enabled:
        return
    mp = _get_mixpanel_client()
    if mp is None:
        return

    try:
        ip = _extract_ip_from_request(request)
        headers = request.headers or {}
        user_agent = get_header_case_insensitive(headers, "user-agent", "") or "N/A"
        distinct_id = _build_distinct_id(ip, user_agent, "N/A")

        props: dict[str, Any] = {"ip": ip, "user_agent": user_agent}
        if properties:
            props.update(properties)

        meta = {"ip": ip} if ip else None
        if meta is not None:
            mp.track(distinct_id, event_name, props, meta=meta)  # type: ignore[call-arg]
        else:
            mp.track(distinct_id, event_name, props)
    except Exception as exc:  # pragma: no cover - do not break flow
        logger.debug("Mixpanel tracking failed for %s: %s", event_name, exc)


def track_tool_invocation(
    ctx: Any,
    tool_name: str,
    tool_args: dict[str, Any],
    client_meta: ClientMeta | None = None,
    auth_origin: AuthOrigin | None = None,
    api_key_fingerprint: str | None = None,
) -> None:
    """Track a tool invocation in Mixpanel, if enabled and in HTTP mode.

    ``auth_origin`` is the pre-computed origin threaded in by the caller — the
    observability paths derive the auth signals once per invocation (via
    :func:`blockscout_mcp_server.telemetry.resolve_auth_signals`) and reuse them
    for both this sink and the community report, so the origin is never
    re-derived here. A ``None`` value — which ``resolve_auth_signals`` yields
    when derivation is skipped or degrades — is recorded as
    ``AUTH_ORIGIN_UNKNOWN``, mirroring :func:`track_community_usage`. Re-deriving
    from ``ctx`` at this point would re-run the very computation that just failed
    and lose the whole event, so it is deliberately avoided.

    ``api_key_fingerprint`` is likewise threaded, pre-computed, and never
    re-derived here — same contract as ``auth_origin``. On this direct path it
    selects the fingerprint identity basis if and only if ``auth_origin ==
    "client"`` **and** a fingerprint was actually provided; every other
    combination (``"server"``, ``"none"``, an unknown/``None`` origin, or a
    ``client`` origin with a missing fingerprint) keeps the legacy IP/name/version
    composite. This is deliberately narrower than the community path
    (:func:`track_community_usage`), which uses any present fingerprint
    regardless of origin: on the direct path the server's own configured key is
    shared by every anonymous caller, so using its fingerprint here would
    collapse them all into a single Mixpanel identity. Only a caller-supplied key
    genuinely distinguishes anyone on this path. A ``client`` origin paired with
    ``None`` fingerprint cannot happen when signals come from
    :func:`blockscout_mcp_server.telemetry.resolve_auth_signals` (its branches
    pair origin and fingerprint atomically), but this sink does not rely on that
    caller contract and degrades to the legacy basis instead of raising.
    """
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

        # Fingerprint basis only when the caller-supplied key is what produced it (auth_origin
        # == "client"); the shared server key must never collapse all anonymous callers into one
        # identity (see the docstring above for the full rationale).
        if auth_origin == "client" and api_key_fingerprint:
            distinct_id = _build_fingerprint_distinct_id(api_key_fingerprint)
        else:
            distinct_id = _build_distinct_id(ip, client_name, client_version)

        properties: dict[str, Any] = {
            "ip": ip,
            "client_name": client_name,
            "client_version": client_version,
            "user_agent": user_agent,
            "tool_args": tool_args,
            "protocol_version": protocol_version,
            "source": _determine_call_source(ctx),
            "auth_origin": auth_origin if auth_origin is not None else AUTH_ORIGIN_UNKNOWN,
        }

        meta = {"ip": ip} if ip else None
        # Mixpanel Python SDK allows meta for IP geolocation mapping
        if meta is not None:
            mp.track(distinct_id, tool_name, properties, meta=meta)  # type: ignore[call-arg]
        else:
            mp.track(distinct_id, tool_name, properties)
    except Exception as exc:  # pragma: no cover - do not break tool flow
        logger.debug("Mixpanel tracking failed for %s: %s", tool_name, exc)


def track_resource_read(
    ctx: Any,
    uri: str,
    client_meta: ClientMeta | None = None,
    auth_origin: AuthOrigin | None = None,
    api_key_fingerprint: str | None = None,
) -> None:
    """Track a resource read in Mixpanel, if enabled and in HTTP mode.

    Delegates to :func:`track_tool_invocation` using the ``RESOURCE_READ`` event
    sentinel so that all gating logic (HTTP-mode, token, IP extraction, etc.) is
    reused verbatim.  The caller is responsible for providing a fully-normalised
    URI string — this function does not stringify.  ``auth_origin`` and
    ``api_key_fingerprint`` are threaded through to :func:`track_tool_invocation`
    unchanged (see its docstring for the identity-basis selection rule) so the
    resource observability path also derives the auth signals only once per read.
    """
    track_tool_invocation(
        ctx,
        RESOURCE_READ_EVENT,
        {"uri": uri},
        client_meta=client_meta,
        auth_origin=auth_origin,
        api_key_fingerprint=api_key_fingerprint,
    )


def track_community_usage(report: ToolUsageReport, ip: str, user_agent: str) -> None:
    """Track a tool invocation from a community (self-hosted) server.

    ``distinct_id`` is keyed on the report's ``api_key_fingerprint`` whenever one is
    present, regardless of ``auth_origin`` — unlike the direct path (see
    :func:`track_tool_invocation`), a community report's server-key fingerprint
    identifies a self-hosted installation and a client-key fingerprint identifies
    that installation's individual users, so either is a meaningful identity here.
    The ``ToolUsageReport`` validator (``_tolerate_malformed_fingerprint``) already
    guarantees present ⇒ valid 64-hex, so no shape-checking is needed at this call
    site. Reports without a fingerprint keep using the legacy ip/client composite so
    legacy reporters are still counted.
    """
    if not _is_http_mode_enabled:
        return
    mp = _get_mixpanel_client()
    if mp is None:
        return

    try:
        if report.api_key_fingerprint:
            distinct_id = _build_fingerprint_distinct_id(report.api_key_fingerprint)
        else:
            distinct_id = _build_distinct_id(ip, report.client_name, report.client_version)

        properties: dict[str, Any] = {
            "ip": ip,
            "client_name": report.client_name,
            "client_version": report.client_version,
            "user_agent": user_agent,
            "tool_args": report.tool_args,
            "protocol_version": report.protocol_version,
            "source": "community",
            "auth_origin": report.auth_origin if report.auth_origin is not None else AUTH_ORIGIN_UNKNOWN,
        }

        meta = {"ip": ip} if ip else None
        if meta is not None:
            mp.track(distinct_id, report.tool_name, properties, meta=meta)  # type: ignore[call-arg]
        else:
            mp.track(distinct_id, report.tool_name, properties)
    except Exception as exc:  # pragma: no cover - do not break flow
        logger.debug("Community Mixpanel tracking failed for %s: %s", report.tool_name, exc)
