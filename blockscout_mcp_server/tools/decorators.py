import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

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

        client_name = "N/A"
        client_version = "N/A"
        protocol_version = "Unknown"

        try:
            if client_params := ctx.session.client_params:
                protocol_version = str(client_params.protocolVersion or "Unknown")
                if client_info := client_params.clientInfo:
                    client_name = client_info.name or "N/A"
                    client_version = client_info.version or "N/A"
        except AttributeError:
            pass

        log_message = (
            f"Tool invoked: {func.__name__} with args: {arg_dict} "
            f"(Client: {client_name}, Version: {client_version}, Protocol: {protocol_version})"
        )
        logger.info(log_message)
        return await func(*args, **kwargs)

    return wrapper
