# SPDX-License-Identifier: LicenseRef-Blockscout
"""Cross-cutting observability helper for MCP resource reads.

Provides :func:`log_resource_read`, the single entry point called by both MCP
resource-read and REST skill-mirror transports on a successful read.  It emits
a structured INFO log line and fans out to the direct-analytics and
community-telemetry sinks, mirroring the failure-isolation shape of
:func:`~blockscout_mcp_server.tools.decorators.log_tool_invocation`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from blockscout_mcp_server import analytics, telemetry
from blockscout_mcp_server.client_meta import (
    UNDEFINED_CLIENT_NAME,
    UNDEFINED_CLIENT_VERSION,
    UNKNOWN_PROTOCOL_VERSION,
    ClientMeta,
    extract_client_meta_from_ctx,
    format_client_meta_suffix,
)
from blockscout_mcp_server.resources import skill_resources

logger = logging.getLogger(__name__)


def log_resource_read(uri: Any, ctx: Any) -> None:
    """Emit a log line and fan out to analytics/telemetry sinks on a successful resource read.

    Parameters
    ----------
    uri:
        The resource URI.  Accepts both ``str`` and pydantic ``AnyUrl`` — it is
        normalised to ``str`` at the top of this helper so both sinks always
        receive a JSON-serialisable value.
    ctx:
        The MCP context (or a REST mock context).  Passed through to the sinks
        for client-metadata and IP extraction.
    """
    # Normalise to str once; AnyUrl is not JSON-serialisable.
    full_uri = str(uri)

    # Extract client metadata up-front.  extract_client_meta_from_ctx already
    # self-guards, but wrap in a try/except so that a future regression never
    # propagates into the request path; fall back to sentinel defaults so the
    # read is still observed.
    try:
        meta: ClientMeta = extract_client_meta_from_ctx(ctx)
    except Exception:
        meta = ClientMeta(
            UNDEFINED_CLIENT_NAME,
            UNDEFINED_CLIENT_VERSION,
            UNKNOWN_PROTOCOL_VERSION,
            "",
            {},
        )

    # Step 1 — human log line.  All label-derivation and formatting in its own
    # guard so a failure here never skips the two sink steps below.
    try:
        rel = skill_resources.uri_to_relative_path(full_uri)
        label = f"skill/{rel}" if rel is not None else full_uri
        suffix = format_client_meta_suffix(meta)
        logger.info("Resource read: %s %s", label, suffix)
    except Exception:
        pass

    # Derive the auth-origin / fingerprint signals once and reuse them for both
    # sinks below (mirrors @log_tool_invocation). telemetry.resolve_auth_signals
    # centralizes the single ctx extraction + SHA-256, the defensive guard, and the
    # all-telemetry-disabled short-circuit shared verbatim with the tool path. The
    # (None, None) fallback degrades gracefully — the analytics sink records the
    # origin as AUTH_ORIGIN_UNKNOWN, the report omits the hash.
    auth_origin, api_key_fingerprint = telemetry.resolve_auth_signals(ctx)

    # Step 2 — direct analytics sink (self-gating, synchronous).
    try:
        analytics.track_resource_read(ctx, full_uri, client_meta=meta, auth_origin=auth_origin)
    except Exception:
        pass

    # Step 3 — community-telemetry sink (fire-and-forget).  The separate guard
    # means an absent event loop or a scheduling failure can never raise into
    # the caller.
    #
    # The task reference is intentionally NOT retained. This is best-effort
    # telemetry, and we deliberately mirror @log_tool_invocation's idiom
    # (`asyncio.create_task(...)` inside try/except — tools/decorators.py) so the
    # tool and resource observability paths never drift in implementation. Both
    # production call sites — the async MCP `read_resource` override and the async
    # REST `serve_skill_resource` handler — always run inside a live event loop,
    # so the orphan-coroutine / no-loop path cannot occur there. Do NOT "fix" this
    # to store the task or switch to get_running_loop() on this path alone (RUF006):
    # that would re-introduce exactly the tool-vs-resource drift this feature prevents.
    try:
        asyncio.create_task(
            telemetry.send_community_resource_report(
                full_uri,
                meta.name,
                meta.version,
                meta.protocol,
                auth_origin=auth_origin,
                api_key_fingerprint=api_key_fingerprint,
            )
        )
    except Exception:
        pass
