"""Client metadata extraction and defaults shared across logging and analytics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blockscout_mcp_server.config import config

UNDEFINED_CLIENT_NAME = "N/A"
UNDEFINED_CLIENT_VERSION = "N/A"
UNKNOWN_PROTOCOL_VERSION = "Unknown"


@dataclass
class ClientMeta:
    name: str
    version: str
    protocol: str
    user_agent: str


def get_header_case_insensitive(headers: Any, key: str, default: str = "") -> str:
    """Return a header value in a case-insensitive way.

    Works with Starlette's `Headers` (already case-insensitive) and plain dicts.
    """
    try:
        value = headers.get(key, None)  # type: ignore[call-arg]
        if value is not None:
            return value
    except Exception:  # pragma: no cover - tolerate any mapping shape
        pass
    try:
        lower_key = key.lower()
        items = headers.items() if hasattr(headers, "items") else []  # type: ignore[assignment]
        for k, v in items:  # type: ignore[assignment]
            if isinstance(k, str) and k.lower() == lower_key:
                return v
    except Exception:  # pragma: no cover - tolerate any mapping shape
        pass
    return default


def _parse_intermediary_header(value: str, allowlist_raw: str) -> str:
    """Normalize and validate an intermediary header value.

    Extracts the first non-empty entry from a comma-separated list, normalizes whitespace,
    guards against invalid characters or length, and ensures the value is allowlisted.
    Returns the normalized value if valid, otherwise an empty string.
    """
    if not value:
        return ""
    first_value = next(
        (stripped for v in value.split(",") if (stripped := v.strip())),
        "",
    )
    if not first_value:
        return ""
    normalized = " ".join(first_value.split())
    if len(normalized) > 16:
        return ""
    if "/" in normalized:
        return ""
    if any(ord(c) < 32 or ord(c) == 127 for c in normalized):
        return ""
    allowlist = [stripped.lower() for v in allowlist_raw.split(",") if (stripped := v.strip())]
    if normalized.lower() not in allowlist:
        return ""
    return normalized


def extract_client_meta_from_ctx(ctx: Any) -> ClientMeta:
    """Extract client meta (name, version, protocol, user_agent) from an MCP Context.

    - name: MCP client name. If unavailable, defaults to "N/A" constant or falls back to user agent.
            If an intermediary HTTP header is present, it is appended to the client name.
    - version: MCP client version. If unavailable, defaults to "N/A" constant.
    - protocol: MCP protocol version. If unavailable, defaults to "Unknown" constant.
    - user_agent: Extracted from HTTP request headers if available.
    """
    client_name = UNDEFINED_CLIENT_NAME
    client_version = UNDEFINED_CLIENT_VERSION
    protocol: str = UNKNOWN_PROTOCOL_VERSION
    user_agent: str = ""
    intermediary: str = ""

    try:
        client_params = getattr(getattr(ctx, "session", None), "client_params", None)
        if client_params is not None:
            # protocolVersion may be missing
            if getattr(client_params, "protocolVersion", None):
                protocol = str(client_params.protocolVersion)
            client_info = getattr(client_params, "clientInfo", None)
            if client_info is not None:
                if getattr(client_info, "name", None):
                    client_name = client_info.name
                if getattr(client_info, "version", None):
                    client_version = client_info.version
        # Read User-Agent from HTTP request (if present)
        request = getattr(getattr(ctx, "request_context", None), "request", None)
        if request is not None:
            headers = request.headers or {}
            user_agent = get_header_case_insensitive(headers, "user-agent", "")
            header_name = config.intermediary_header
            allowlist_raw = config.intermediary_allowlist
            if header_name and allowlist_raw:
                intermediary_raw = get_header_case_insensitive(headers, header_name, "")
                intermediary = _parse_intermediary_header(intermediary_raw, allowlist_raw)
        # If client name is still undefined, fallback to User-Agent
        if client_name == UNDEFINED_CLIENT_NAME and user_agent:
            client_name = user_agent
        if intermediary:
            client_name = f"{client_name}/{intermediary}"
    except Exception:  # pragma: no cover - tolerate any ctx shape
        pass

    return ClientMeta(name=client_name, version=client_version, protocol=protocol, user_agent=user_agent)
