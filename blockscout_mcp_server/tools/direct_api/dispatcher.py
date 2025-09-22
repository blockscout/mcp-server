"""Dispatcher for direct_api_call tool to route to specialized handlers."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

# The registry will store tuples of (regex_pattern, handler_function)
HANDLER_REGISTRY: list[tuple[re.Pattern[str], Callable[..., Awaitable[Any]]]] = []


def register_handler(path_regex: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """A decorator to register a specialized handler for a given URL path regex."""

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        HANDLER_REGISTRY.append((re.compile(path_regex), func))
        return func

    return decorator


async def dispatch(endpoint_path: str, **kwargs: Any) -> Any | None:
    """Find and execute the first matching handler for the given endpoint path."""
    for path_regex, handler in HANDLER_REGISTRY:
        match = path_regex.fullmatch(endpoint_path)
        if match:
            return await handler(match=match, **kwargs)
    return None
