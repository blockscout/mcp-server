"""Dispatcher for direct_api_call tool to route to specialized handlers."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class DirectApiHandler(Protocol):
    """Protocol describing the expected handler signature."""

    def __call__(
        self,
        *,
        match: re.Match[str],
        query_params: dict[str, Any] | None,
        **kwargs: Any,
    ) -> Awaitable[Any]:
        """Handle the dispatched response."""


# The registry will store tuples of (regex_pattern, handler_function)
HANDLER_REGISTRY: list[tuple[re.Pattern[str], DirectApiHandler]] = []


def register_handler(path_regex: str) -> Callable[[DirectApiHandler], DirectApiHandler]:
    """A decorator to register a specialized handler for a given URL path regex."""

    def decorator(func: DirectApiHandler) -> DirectApiHandler:
        HANDLER_REGISTRY.append((re.compile(path_regex), func))
        return func

    return decorator


async def dispatch(
    endpoint_path: str,
    *,
    query_params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any | None:
    """Find and execute the first matching handler for the given endpoint path.

    Args:
        endpoint_path: The API path that was requested.
        query_params: The query parameters used in the upstream API request (if any).
        **kwargs: Additional context forwarded to the handler.

    Note: precedence follows registration order. Keep regex patterns disjoint or
    register the most specific handler first when overlap is unavoidable.
    """
    for path_regex, handler in HANDLER_REGISTRY:
        match = path_regex.fullmatch(endpoint_path)
        if match:
            return await handler(match=match, query_params=query_params, **kwargs)
    return None
