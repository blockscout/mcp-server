"""Dependencies for the REST API, such as mock context providers."""


class MockCtx:
    """A mock context object that provides no-op implementations for MCP context methods."""

    async def info(self, message: str) -> None:
        """A no-op info method."""
        return None

    async def report_progress(self, *args, **kwargs) -> None:
        """A no-op report_progress method."""
        return None


def get_mock_context() -> MockCtx:
    """Dependency provider to get a mock context for stateless REST calls."""
    return MockCtx()
