"""Dependencies for the REST API, such as mock context providers."""


class MockCtx:
    """A mock context for stateless REST calls.

    Tool functions require a ``ctx`` object to report progress. Since REST
    endpoints are stateless and have no MCP session, this mock provides the
    required ``info`` and ``report_progress`` methods as no-op async functions.
    """

    async def info(self, message: str) -> None:
        """Simulate the ``info`` method of an MCP ``Context``."""
        pass

    async def report_progress(self, *args, **kwargs) -> None:
        """Simulate the ``report_progress`` method of an MCP ``Context``."""
        pass


def get_mock_context() -> MockCtx:
    """Dependency provider to get a mock context for stateless REST calls."""
    return MockCtx()
