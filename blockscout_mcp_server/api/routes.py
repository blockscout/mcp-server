"""Module for registering all REST API routes with the FastMCP server."""

import pathlib

import anyio
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

# Define paths to static files relative to this file's location
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
LLMS_TXT_PATH = BASE_DIR / "llms.txt"


async def health_check(_: Request) -> Response:
    """Return a simple health status."""
    return JSONResponse({"status": "ok"})


async def serve_llms_txt(_: Request) -> Response:
    """Serve the llms.txt file."""
    try:
        content = await anyio.Path(LLMS_TXT_PATH).read_text(encoding="utf-8")
    except OSError as exc:
        message = f"Failed to read llms.txt: {exc}"
        return PlainTextResponse(message, status_code=500)
    return PlainTextResponse(content)


async def main_page(_: Request) -> Response:
    """Serve the main landing page."""
    file_path = TEMPLATES_DIR / "index.html"
    try:
        content = await anyio.Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        message = f"Failed to read landing page: {exc}"
        return PlainTextResponse(message, status_code=500)
    return HTMLResponse(content)


def register_api_routes(mcp: FastMCP) -> None:
    """Registers all REST API routes."""
    # These routes are not part of the OpenAPI schema for tools.
    mcp.custom_route("/health", methods=["GET"], include_in_schema=False)(health_check)
    mcp.custom_route("/llms.txt", methods=["GET"], include_in_schema=False)(serve_llms_txt)
    mcp.custom_route("/", methods=["GET"], include_in_schema=False)(main_page)
