"""Module for registering all REST API routes with the FastMCP server."""

import pathlib

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

# Define paths to static files relative to this file's location
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
LLMS_TXT_PATH = BASE_DIR / "llms.txt"

# Preload static content at module import
try:
    INDEX_HTML_CONTENT = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - test will not cover missing file
    INDEX_HTML_CONTENT = None
    print(f"Warning: Failed to preload landing page content: {exc}")

try:
    LLMS_TXT_CONTENT = LLMS_TXT_PATH.read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - test will not cover missing file
    LLMS_TXT_CONTENT = None
    print(f"Warning: Failed to preload llms.txt content: {exc}")


async def health_check(_: Request) -> Response:
    """Return a simple health status."""
    return JSONResponse({"status": "ok"})


async def serve_llms_txt(_: Request) -> Response:
    """Serve the llms.txt file."""
    if LLMS_TXT_CONTENT is None:
        message = "llms.txt content is not available."
        return PlainTextResponse(message, status_code=500)
    return PlainTextResponse(LLMS_TXT_CONTENT)


async def main_page(_: Request) -> Response:
    """Serve the main landing page."""
    if INDEX_HTML_CONTENT is None:
        message = "Landing page content is not available."
        return PlainTextResponse(message, status_code=500)
    return HTMLResponse(INDEX_HTML_CONTENT)


def register_api_routes(mcp: FastMCP) -> None:
    """Registers all REST API routes."""
    # These routes are not part of the OpenAPI schema for tools.
    mcp.custom_route("/health", methods=["GET"], include_in_schema=False)(health_check)
    mcp.custom_route("/llms.txt", methods=["GET"], include_in_schema=False)(serve_llms_txt)
    mcp.custom_route("/", methods=["GET"], include_in_schema=False)(main_page)
