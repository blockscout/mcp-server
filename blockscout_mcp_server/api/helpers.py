"""Shared utilities for REST API route handlers."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def str_to_bool(val: str) -> bool:
    """Convert a string to a boolean value."""
    return val.lower() in ("true", "1", "t", "yes")


# A map of parameter names to their type conversion functions.
# All other parameters are assumed to be strings.
PARAM_TYPES: dict[str, Callable[[str], Any]] = {
    "include_transactions": str_to_bool,
    "include_raw_input": str_to_bool,
}


def extract_and_validate_params(request: Request, required: list[str], optional: list[str]) -> dict[str, Any]:
    """Extract and validate query parameters from a request.

    Args:
        request: The Starlette request object.
        required: A list of required parameter names.
        optional: A list of optional parameter names.

    Returns:
        A dictionary of validated parameters.

    Raises:
        ValueError: If a required parameter is missing.
    """
    params: dict[str, Any] = {}
    query_params = request.query_params

    for name in required:
        value = query_params.get(name)
        if value is None:
            raise ValueError(f"Missing required query parameter: '{name}'")
        params[name] = PARAM_TYPES.get(name, str)(value)

    for name in optional:
        value = query_params.get(name)
        if value is not None:
            params[name] = PARAM_TYPES.get(name, str)(value)

    return params


def handle_validation_errors(
    func: Callable[[Request], Awaitable[Response]],
) -> Callable[[Request], Awaitable[Response]]:
    """Decorator to catch ValueErrors and return a 400 Bad Request response."""

    @wraps(func)
    async def wrapper(request: Request) -> Response:
        try:
            return await func(request)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    return wrapper
