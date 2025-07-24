"""Logging utilities for the Blockscout MCP Server."""

import logging
import sys


def replace_rich_handlers_with_standard() -> None:
    """Replace any Rich logging handlers with standard StreamHandlers.

    This function scans all existing loggers and replaces Rich handlers
    with standard Python logging StreamHandlers to prevent multi-line
    log formatting that's not suitable for production environments.
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
                logger = logging.getLogger(__name__)
                logger.debug(f"Skipping handler inspection due to error: {e}")
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
                error_logger = logging.getLogger(__name__)
                error_logger.warning(f"Failed to replace Rich handler {rich_handler}: {e}")
                continue

    if handlers_replaced > 0:
        # Use the new standard logger to report success
        logger = logging.getLogger(__name__)
        logger.info(f"Replaced {handlers_replaced} Rich logging handlers with standard handlers")
