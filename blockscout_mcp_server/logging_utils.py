# SPDX-License-Identifier: LicenseRef-Blockscout
"""Logging utilities for the Blockscout MCP Server."""

import logging
import sys

import anyio

# Pre-define module logger to avoid circular dependencies during logging system manipulation
# This logger is created before any handler manipulation occurs, ensuring safe error reporting
_module_logger = logging.getLogger(__name__)

# The MCP SDK's stateless streamable-HTTP session manager logs a broad "Stateless session
# crashed" ERROR record (with a nested-ExceptionGroup traceback) whenever a client aborts the
# HTTP request while a tool call is still running. Nothing is actually broken in that case: the
# SDK's per-request transport streams are closed while the detached tool call keeps running, and
# writing its eventual result to the closed stream raises anyio.ClosedResourceError. The logger
# name below is the exact interception point for that record (mcp 1.26,
# mcp/server/streamable_http_manager.py).
CLIENT_DISCONNECT_LOGGER_NAME = "mcp.server.streamable_http_manager"
CLIENT_DISCONNECT_RECORD_MESSAGE = "Stateless session crashed"


class ClientDisconnectFilter(logging.Filter):
    """Demote the SDK's "client disconnected mid-call" record to a one-line DEBUG record.

    This filter never drops records - it always returns True. It only recognizes the exact
    "Stateless session crashed" record shape whose exception tree consists solely of
    anyio.ClosedResourceError leaves (following BaseExceptionGroup children only, never
    __cause__/__context__ chains), and mutates that record in place so it renders as a single
    DEBUG line without a traceback. Every other record - including the SDK's stateful crash
    record and any exception tree that contains an unrelated exception - passes through
    untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Demote the matching record in place; always return True."""
        if record.getMessage() != CLIENT_DISCONNECT_RECORD_MESSAGE:
            return True

        if not record.exc_info or record.exc_info[1] is None:
            return True

        exception = record.exc_info[1]
        if not self._all_leaves_are_closed_resource_error(exception):
            return True

        record.levelno = logging.DEBUG
        record.levelname = logging.getLevelName(logging.DEBUG)
        record.msg = "Stateless session closed by client disconnect (anyio.ClosedResourceError); traceback suppressed."
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True

    @staticmethod
    def _all_leaves_are_closed_resource_error(exception: BaseException) -> bool:
        """Return True if every leaf of the exception tree is anyio.ClosedResourceError.

        A BaseExceptionGroup node contributes its `.exceptions` children; anything else is a
        leaf. __cause__/__context__ chains are deliberately not followed.
        """
        if isinstance(exception, BaseExceptionGroup):
            children = exception.exceptions
            return len(children) > 0 and all(
                ClientDisconnectFilter._all_leaves_are_closed_resource_error(child) for child in children
            )
        return isinstance(exception, anyio.ClosedResourceError)


def install_client_disconnect_filter(logger_name: str = CLIENT_DISCONNECT_LOGGER_NAME) -> None:
    """Attach a ClientDisconnectFilter to the given logger, unless one is already attached.

    The default logger name is the MCP SDK's stateless session-manager logger. An explicit
    logger_name is accepted for testability, so unit tests can exercise this against a
    throwaway logger instead of mutating the real, process-global SDK logger.
    """
    logger = logging.getLogger(logger_name)
    if not any(isinstance(existing_filter, ClientDisconnectFilter) for existing_filter in logger.filters):
        logger.addFilter(ClientDisconnectFilter())


def replace_rich_handlers_with_standard() -> None:
    """Replace any Rich logging handlers with standard StreamHandlers.

    This function scans all existing loggers and replaces Rich handlers
    with standard Python logging StreamHandlers to prevent multi-line
    log formatting that's not suitable for production environments.

    Note: Uses defensive logging practices to avoid circular dependencies.
    Since this function manipulates the logging system itself, it uses a
    pre-defined module logger and fallback mechanisms to ensure safe error
    reporting even if the logging system is in an inconsistent state.
    """
    # Standard log format that matches our desired output
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Get all existing loggers
    loggers_to_process = [logging.getLogger()]  # Start with root logger

    # Add all named loggers
    for name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(name)
        if logger != logging.getLogger():  # Skip root logger (already added)
            loggers_to_process.append(logger)

    handlers_replaced = 0

    for logger in loggers_to_process:
        # Check each handler to see if it's a Rich handler
        handlers_to_replace = []

        for handler in logger.handlers[:]:  # Copy list to avoid modification during iteration
            # Check if this is a Rich handler by looking at the class name or module
            try:
                handler_class_name = handler.__class__.__name__
                handler_module = getattr(handler.__class__, "__module__", "")

                # Ensure both values are strings before calling .lower()
                if (isinstance(handler_class_name, str) and "rich" in handler_class_name.lower()) or (
                    isinstance(handler_module, str) and "rich" in handler_module.lower()
                ):
                    handlers_to_replace.append(handler)
            except (AttributeError, TypeError, ValueError) as e:
                # If handler has unexpected attributes or missing properties, skip it gracefully
                # This ensures we continue processing other handlers even if one is problematic
                try:
                    _module_logger.debug(f"Skipping handler inspection due to error: {e}")
                except Exception:
                    # Fallback if logging system is unstable - use direct stderr output
                    print(f"Warning: Skipping handler inspection due to error: {e}", file=sys.stderr)
                continue

        # Replace Rich handlers with standard StreamHandlers
        for rich_handler in handlers_to_replace:
            try:
                # Remove the Rich handler
                logger.removeHandler(rich_handler)

                # Create a replacement StreamHandler
                new_handler = logging.StreamHandler(sys.stderr)
                new_handler.setLevel(rich_handler.level)
                new_handler.setFormatter(formatter)

                # Add the new handler
                logger.addHandler(new_handler)
                handlers_replaced += 1
            except (AttributeError, ValueError, OSError, RuntimeError) as e:
                # Handle various failures that can occur during handler manipulation:
                # - AttributeError: Missing handler attributes or methods
                # - ValueError: Invalid handler state or configuration
                # - OSError: Permission issues or file system problems
                # - RuntimeError: Threading issues or handler state conflicts
                try:
                    _module_logger.warning(f"Failed to replace Rich handler {rich_handler}: {e}")
                except Exception:
                    # Fallback if logging system is unstable - use direct stderr output
                    print(f"Warning: Failed to replace Rich handler {rich_handler}: {e}", file=sys.stderr)
                continue

    if handlers_replaced > 0:
        # Use the pre-defined module logger to report success
        try:
            _module_logger.info(f"Replaced {handlers_replaced} Rich logging handlers with standard handlers")
        except Exception:
            # Fallback if logging system is unstable - use direct stderr output
            print(f"Info: Replaced {handlers_replaced} Rich logging handlers with standard handlers", file=sys.stderr)
