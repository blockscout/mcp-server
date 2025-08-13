"""Dependencies for the REST API, such as mock context providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from starlette.requests import Request


class _RequestContextWrapper:
    """Lightweight wrapper to mimic MCP's request_context shape for analytics."""

    def __init__(self, request: Request) -> None:
        self.request: Request = request


class MockCtx:
    """A mock context for stateless REST calls.

    Tool functions require a ``ctx`` object to report progress. Since REST
    endpoints are stateless and have no MCP session, this mock provides the
    required ``info`` and ``report_progress`` methods as no-op async functions.
    It also exposes a ``request_context`` with the current Starlette request so
    analytics can extract connection fingerprint data.
    """

    def __init__(self, request: Request | None = None) -> None:
        self.request_context = _RequestContextWrapper(request) if request is not None else None
        # Mark source explicitly so analytics can distinguish REST from MCP without path coupling
        self.call_source = "rest"

    async def info(self, message: str) -> None:
        """Simulate the ``info`` method of an MCP ``Context``."""
        pass

    async def report_progress(self, *args, **kwargs) -> None:
        """Simulate the ``report_progress`` method of an MCP ``Context``."""
        pass


def get_mock_context(request: Request | None = None) -> MockCtx:
    """Dependency provider to get a mock context for stateless REST calls."""
    return MockCtx(request=request)
