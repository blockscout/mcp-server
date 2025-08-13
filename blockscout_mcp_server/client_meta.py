"""Client metadata extraction and defaults shared across logging and analytics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def extract_client_meta_from_ctx(ctx: Any) -> ClientMeta:
    """Extract client meta (name, version, protocol, user_agent) from an MCP Context.

    - name: MCP client name. If unavailable, defaults to "N/A" constant or falls back to user agent.
    - version: MCP client version. If unavailable, defaults to "N/A" constant.
    - protocol: MCP protocol version. If unavailable, defaults to "Unknown" constant.
    - user_agent: Extracted from HTTP request headers if available.
    """
    client_name = UNDEFINED_CLIENT_NAME
    client_version = UNDEFINED_CLIENT_VERSION
    protocol: str = UNKNOWN_PROTOCOL_VERSION
    user_agent: str = ""

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
        # If client name is still undefined, fallback to User-Agent
        if client_name == UNDEFINED_CLIENT_NAME and user_agent:
            client_name = user_agent
    except Exception:  # pragma: no cover - tolerate any ctx shape
        pass

    return ClientMeta(name=client_name, version=client_version, protocol=protocol, user_agent=user_agent)
