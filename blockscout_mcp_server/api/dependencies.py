"""Dependencies for the REST API, such as mock context providers."""


class _RequestContextWrapper:
    """Lightweight wrapper to mimic MCP's request_context shape for analytics."""

    def __init__(self, request) -> None:  # type: ignore[no-untyped-def]
        self.request = request


class MockCtx:
    """A mock context for stateless REST calls.

    Tool functions require a ``ctx`` object to report progress. Since REST
    endpoints are stateless and have no MCP session, this mock provides the
    required ``info`` and ``report_progress`` methods as no-op async functions.
    It also exposes a ``request_context`` with the current Starlette request so
    analytics can extract connection fingerprint data.
    """

    def __init__(self, request=None) -> None:  # type: ignore[no-untyped-def]
        self.request_context = _RequestContextWrapper(request) if request is not None else None
        # Mark source explicitly so analytics can distinguish REST from MCP without path coupling
        self.call_source = "rest"

    async def info(self, message: str) -> None:
        """Simulate the ``info`` method of an MCP ``Context``."""
        pass

    async def report_progress(self, *args, **kwargs) -> None:
        """Simulate the ``report_progress`` method of an MCP ``Context``."""
        pass


def get_mock_context(request=None) -> MockCtx:  # type: ignore[no-untyped-def]
    """Dependency provider to get a mock context for stateless REST calls."""
    return MockCtx(request=request)
