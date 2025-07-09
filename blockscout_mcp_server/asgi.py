"""Main ASGI application for the Blockscout MCP Server.

This file initializes the FastAPI app used for all HTTP-based modes,
managing the MCP session manager's lifecycle and mounting the existing
MCP-over-HTTP app.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from blockscout_mcp_server.server import mcp


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage the MCP session manager's lifecycle."""
    mcp.session_manager.start()
    yield
    await mcp.session_manager.stop()


app = FastAPI(lifespan=lifespan)

# Mount the existing MCP-over-HTTP application
app.mount("/mcp", mcp.streamable_http_app())
