# SPDX-License-Identifier: LicenseRef-Blockscout
import asyncio
import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from blockscout_mcp_server import analytics, telemetry
from blockscout_mcp_server.client_meta import extract_client_meta_from_ctx, format_client_meta_suffix

logger = logging.getLogger(__name__)

# Placeholder that replaces a live `session_id` value before it reaches any
# observability sink (INFO log line, Mixpanel `tool_args`, community-telemetry
# payload). A `session_id` is live capability material — whoever holds it can
# spend its budget — so it gets the same treatment the PRO API key already
# gets elsewhere (never forwarded raw to a sink). Presence-vs-absence is left
# observable: only a present, non-empty value is masked.
_SESSION_ID_REDACTED_PLACEHOLDER = "<redacted>"


def log_tool_invocation(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Log the tool name and arguments when it is invoked."""
    sig = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arg_dict = dict(bound.arguments)
        ctx = arg_dict.pop("ctx", None)

        # Mask a live `session_id` before it reaches the log line, analytics, or
        # telemetry sinks below — all three read this same `arg_dict`. Masking is
        # unconditional by argument name (not gated on the session feature being
        # enabled), since ungated deployments also receive this argument.
        if arg_dict.get("session_id"):
            arg_dict["session_id"] = _SESSION_ID_REDACTED_PLACEHOLDER

        # Extract client metadata consistently using shared helper
        meta = extract_client_meta_from_ctx(ctx)
        client_name = meta.name
        client_version = meta.version
        protocol_version = meta.protocol

        # Derive the auth-origin / fingerprint signals once and reuse them for both
        # sinks below; see telemetry.resolve_auth_signals for the rationale and gating.
        auth_origin, api_key_fingerprint = telemetry.resolve_auth_signals(ctx)

        # Track analytics (no-op if disabled)
        try:
            analytics.track_tool_invocation(
                ctx,
                func.__name__,
                arg_dict,
                client_meta=meta,
                auth_origin=auth_origin,
                api_key_fingerprint=api_key_fingerprint,
            )
        except Exception:
            # Defensive: tracking must never break tool execution
            pass

        log_message = f"Tool invoked: {func.__name__} with args: {arg_dict} " + format_client_meta_suffix(meta)
        logger.info(log_message)

        try:
            return await func(*args, **kwargs)
        finally:
            try:
                arg_snapshot = arg_dict.copy()
                asyncio.create_task(
                    telemetry.send_community_usage_report(
                        func.__name__,
                        arg_snapshot,
                        client_name,
                        client_version,
                        protocol_version,
                        auth_origin=auth_origin,
                        api_key_fingerprint=api_key_fingerprint,
                    )
                )
            except Exception:
                pass

    return wrapper
