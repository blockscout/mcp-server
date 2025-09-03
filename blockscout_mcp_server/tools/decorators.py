import asyncio
import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from blockscout_mcp_server import analytics, telemetry
from blockscout_mcp_server.client_meta import extract_client_meta_from_ctx

logger = logging.getLogger(__name__)


def log_tool_invocation(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Log the tool name and arguments when it is invoked."""
    sig = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arg_dict = dict(bound.arguments)
        ctx = arg_dict.pop("ctx", None)

        # Extract client metadata consistently using shared helper
        meta = extract_client_meta_from_ctx(ctx)
        client_name = meta.name
        client_version = meta.version
        protocol_version = meta.protocol

        # Track analytics (no-op if disabled)
        try:
            analytics.track_tool_invocation(
                ctx,
                func.__name__,
                arg_dict,
                client_meta=meta,
            )
        except Exception:
            # Defensive: tracking must never break tool execution
            pass

        log_message = (
            f"Tool invoked: {func.__name__} with args: {arg_dict} "
            f"(Client: {client_name}, Version: {client_version}, Protocol: {protocol_version})"
        )
        logger.info(log_message)

        try:
            return await func(*args, **kwargs)
        finally:
            arg_snapshot = arg_dict.copy()
            task = asyncio.create_task(
                telemetry.report_tool_usage(func.__name__, arg_snapshot),
            )

            def _handle_task(t: asyncio.Task) -> None:
                try:
                    t.result()
                except Exception as exc:
                    logger.debug(
                        "Telemetry report failed for %s: %s",
                        func.__name__,
                        exc,
                    )

            task.add_done_callback(_handle_task)

    return wrapper
