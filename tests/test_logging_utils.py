"""Unit tests for blockscout_mcp_server.logging_utils module."""

import logging
import sys
from unittest.mock import patch

from blockscout_mcp_server.logging_utils import replace_rich_handlers_with_standard


class MockRichHandler:
    """Mock Rich handler for testing purposes."""

    def __init__(self, level=logging.INFO):
        self.level = level
        # Create a proper mock class with Rich-like attributes
        self._mock_class = type("RichHandler", (), {"__name__": "RichHandler", "__module__": "rich.logging"})

    @property
    def __class__(self):
        return self._mock_class


class MockNonRichHandler:
    """Mock non-Rich handler for testing purposes."""

    def __init__(self, level=logging.INFO):
        self.level = level
        # Create a proper mock class with non-Rich attributes
        self._mock_class = type("StreamHandler", (), {"__name__": "StreamHandler", "__module__": "logging"})

    @property
    def __class__(self):
        return self._mock_class


class MockProblematicHandler:
    """Mock handler that causes errors during inspection."""

    def __init__(self):
        # Create a class that reliably raises AttributeError for __name__ access
        self._problematic_class = self._create_problematic_class()

    def _create_problematic_class(self):
        """Create a class that reliably raises AttributeError when accessing attributes."""

        class ProblematicClass:
            def __getattr__(self, name):
                if name == "__name__":
                    raise AttributeError("'ProblematicClass' object has no attribute '__name__'")
                elif name == "__module__":
                    raise AttributeError("'ProblematicClass' object has no attribute '__module__'")
                raise AttributeError(f"'ProblematicClass' object has no attribute '{name}'")

        return ProblematicClass()

    @property
    def __class__(self):
        return self._problematic_class


class TestReplaceRichHandlersWithStandard:
    """Test suite for replace_rich_handlers_with_standard function."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Store original logger manager state
        self.original_logger_dict = logging.Logger.manager.loggerDict.copy()

    def teardown_method(self):
        """Clean up test environment after each test."""
        # Clear handlers from all loggers to prevent interference
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()

        # Also clear root logger handlers
        logging.getLogger().handlers.clear()

        # Restore original logger manager state
        logging.Logger.manager.loggerDict.clear()
        logging.Logger.manager.loggerDict.update(self.original_logger_dict)

    def test_replaces_rich_handler_with_stream_handler(self):
        """Test that Rich handlers are replaced with StreamHandlers."""
        # Create test logger with Rich handler
        test_logger = logging.getLogger("test_rich_logger")
        rich_handler = MockRichHandler(level=logging.DEBUG)
        test_logger.addHandler(rich_handler)

        # Clear any existing handlers from root logger to isolate test
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers.clear()

        try:
            # Store initial handler count
            initial_handlers = test_logger.handlers[:]
            assert len(initial_handlers) == 1
            assert initial_handlers[0] is rich_handler

            # Run the function
            replace_rich_handlers_with_standard()

            # Verify Rich handler was removed
            assert rich_handler not in test_logger.handlers

            # Verify new StreamHandler was added
            assert len(test_logger.handlers) == 1
            new_handler = test_logger.handlers[0]
            assert isinstance(new_handler, logging.StreamHandler)
            assert new_handler.level == logging.DEBUG  # Should preserve level
            assert new_handler.stream == sys.stderr  # Should use stderr

            # Verify it's a different handler than the original
            assert new_handler is not rich_handler

        finally:
            # Restore original handlers
            root_logger.handlers = original_handlers

    def test_preserves_handler_log_level(self):
        """Test that the log level is preserved when replacing handlers."""
        test_logger = logging.getLogger("test_level_logger")
        rich_handler = MockRichHandler(level=logging.WARNING)
        test_logger.addHandler(rich_handler)

        replace_rich_handlers_with_standard()

        # Verify level was preserved
        assert len(test_logger.handlers) == 1
        new_handler = test_logger.handlers[0]
        assert new_handler.level == logging.WARNING

    def test_applies_correct_formatter(self):
        """Test that the correct formatter is applied to new handlers."""
        test_logger = logging.getLogger("test_formatter_logger")
        rich_handler = MockRichHandler()
        test_logger.addHandler(rich_handler)

        replace_rich_handlers_with_standard()

        # Verify formatter was applied
        new_handler = test_logger.handlers[0]
        assert new_handler.formatter is not None
        assert new_handler.formatter._fmt == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert new_handler.formatter.datefmt == "%Y-%m-%d %H:%M:%S"

    def test_counts_replaced_handlers_correctly(self):
        """Test that the count of replaced handlers is accurate."""
        # Create multiple loggers with Rich handlers
        logger1 = logging.getLogger("test_count_1")
        logger2 = logging.getLogger("test_count_2")

        rich_handler1 = MockRichHandler()
        rich_handler2a = MockRichHandler()
        rich_handler2b = MockRichHandler()

        logger1.addHandler(rich_handler1)
        logger2.addHandler(rich_handler2a)
        logger2.addHandler(rich_handler2b)  # Two handlers on one logger

        replace_rich_handlers_with_standard()

        # Verify all Rich handlers were replaced
        assert rich_handler1 not in logger1.handlers
        assert rich_handler2a not in logger2.handlers
        assert rich_handler2b not in logger2.handlers

        # Verify new StreamHandlers were added
        assert len(logger1.handlers) == 1
        assert len(logger2.handlers) == 2
        assert all(isinstance(h, logging.StreamHandler) for h in logger1.handlers)
        assert all(isinstance(h, logging.StreamHandler) for h in logger2.handlers)

    def test_skips_non_rich_handlers(self):
        """Test that non-Rich handlers are left unchanged."""
        test_logger = logging.getLogger("test_non_rich_logger")
        non_rich_handler = MockNonRichHandler()
        test_logger.addHandler(non_rich_handler)

        replace_rich_handlers_with_standard()

        # Verify non-Rich handler was not removed
        assert non_rich_handler in test_logger.handlers
        assert len(test_logger.handlers) == 1

    def test_handles_mixed_handler_types(self):
        """Test handling loggers with both Rich and non-Rich handlers."""
        test_logger = logging.getLogger("test_mixed_logger")
        rich_handler = MockRichHandler()
        non_rich_handler = MockNonRichHandler()
        test_logger.addHandler(rich_handler)
        test_logger.addHandler(non_rich_handler)

        replace_rich_handlers_with_standard()

        # Should have 2 handlers: new StreamHandler + original non-Rich
        assert len(test_logger.handlers) == 2
        assert rich_handler not in test_logger.handlers
        assert non_rich_handler in test_logger.handlers

        # Verify we have one StreamHandler (replacement) and one non-Rich handler (preserved)
        stream_handlers = [h for h in test_logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1

    def test_handles_empty_logger_list(self):
        """Test behavior when no loggers exist."""
        # Clear all loggers
        logging.Logger.manager.loggerDict.clear()

        # Should not crash
        replace_rich_handlers_with_standard()

        # Function should complete without errors (verified by reaching this point)

    def test_handles_loggers_with_no_handlers(self):
        """Test behavior when loggers have no handlers."""
        test_logger = logging.getLogger("test_no_handlers_logger")
        # Explicitly ensure no handlers
        test_logger.handlers.clear()

        # Should not crash
        replace_rich_handlers_with_standard()

        # Logger should still have no handlers
        assert len(test_logger.handlers) == 0

    def test_handles_handler_inspection_errors_gracefully(self, caplog):
        """Test graceful handling of errors during handler inspection."""
        caplog.set_level(logging.DEBUG)

        test_logger = logging.getLogger("test_inspection_error_logger")
        problematic_handler = MockProblematicHandler()
        test_logger.addHandler(problematic_handler)

        # Should not crash
        replace_rich_handlers_with_standard()

        # Should log debug message about skipping handler
        assert "Skipping handler inspection due to error" in caplog.text

    @patch("logging.StreamHandler")
    def test_handles_handler_creation_errors_gracefully(self, mock_stream_handler, caplog):
        """Test graceful handling of errors during handler creation."""
        # Make StreamHandler creation fail
        mock_stream_handler.side_effect = OSError("Permission denied")

        caplog.set_level(logging.WARNING)

        test_logger = logging.getLogger("test_creation_error_logger")
        rich_handler = MockRichHandler()
        test_logger.addHandler(rich_handler)

        # Should not crash
        replace_rich_handlers_with_standard()

        # Should log warning about failure
        assert "Failed to replace Rich handler" in caplog.text
        assert "Permission denied" in caplog.text

    def test_handles_handler_removal_errors_gracefully(self, caplog):
        """Test graceful handling of errors during handler removal."""
        caplog.set_level(logging.WARNING)

        test_logger = logging.getLogger("test_removal_error_logger")

        # Create a mock handler that causes errors when removed
        problematic_handler = MockRichHandler()
        test_logger.addHandler(problematic_handler)

        # Mock removeHandler to raise an exception
        original_remove = test_logger.removeHandler

        def failing_remove(handler):
            if handler == problematic_handler:
                raise RuntimeError("Handler removal failed")
            return original_remove(handler)

        test_logger.removeHandler = failing_remove

        # Should not crash
        replace_rich_handlers_with_standard()

        # Should log warning about failure
        assert "Failed to replace Rich handler" in caplog.text
        assert "Handler removal failed" in caplog.text

    def test_continues_processing_after_individual_failures(self):
        """Test that processing continues even if individual handler replacement fails."""
        # Create two loggers: one that will fail, one that will succeed
        failing_logger = logging.getLogger("test_failing_logger")
        success_logger = logging.getLogger("test_success_logger")

        failing_handler = MockRichHandler()
        success_handler = MockRichHandler()

        failing_logger.addHandler(failing_handler)
        success_logger.addHandler(success_handler)

        # Make the failing logger's removeHandler method raise an exception
        def failing_remove(handler):
            raise RuntimeError("Simulated failure")

        failing_logger.removeHandler = failing_remove

        replace_rich_handlers_with_standard()

        # Success logger should still be processed successfully
        assert len(success_logger.handlers) == 1
        assert isinstance(success_logger.handlers[0], logging.StreamHandler)
        assert success_handler not in success_logger.handlers

        # Failing logger should still have the original handler
        assert failing_handler in failing_logger.handlers

    def test_rich_detection_by_class_name(self):
        """Test Rich handler detection by class name."""
        test_logger = logging.getLogger("test_class_name_detection")

        # Create handler with "Rich" in class name but different module
        handler = MockNonRichHandler()
        handler.__class__.__name__ = "CustomRichHandler"
        handler.__class__.__module__ = "custom.module"

        test_logger.addHandler(handler)

        replace_rich_handlers_with_standard()

        # Should be detected and replaced due to "Rich" in class name
        assert len(test_logger.handlers) == 1
        assert isinstance(test_logger.handlers[0], logging.StreamHandler)

    def test_rich_detection_by_module_name(self):
        """Test Rich handler detection by module name."""
        test_logger = logging.getLogger("test_module_name_detection")

        # Create handler with "rich" in module name but different class name
        handler = MockNonRichHandler()
        handler.__class__.__name__ = "CustomHandler"
        handler.__class__.__module__ = "rich.custom"

        test_logger.addHandler(handler)

        replace_rich_handlers_with_standard()

        # Should be detected and replaced due to "rich" in module name
        assert len(test_logger.handlers) == 1
        assert isinstance(test_logger.handlers[0], logging.StreamHandler)

    def test_case_insensitive_rich_detection(self):
        """Test that Rich detection is case-insensitive."""
        test_logger = logging.getLogger("test_case_insensitive")

        # Create handler with uppercase "RICH" in names
        handler = MockNonRichHandler()
        handler.__class__.__name__ = "RICHHANDLER"
        handler.__class__.__module__ = "RICH.LOGGING"

        test_logger.addHandler(handler)

        replace_rich_handlers_with_standard()

        # Should be detected and replaced (case-insensitive)
        assert len(test_logger.handlers) == 1
        assert isinstance(test_logger.handlers[0], logging.StreamHandler)

    def test_no_replacement_message_when_no_rich_handlers(self, caplog):
        """Test that function works correctly when no Rich handlers are found."""
        caplog.set_level(logging.INFO)

        test_logger = logging.getLogger("test_no_rich")
        non_rich_handler = MockNonRichHandler()
        test_logger.addHandler(non_rich_handler)

        replace_rich_handlers_with_standard()

        # Non-Rich handler should remain unchanged
        assert non_rich_handler in test_logger.handlers
        assert len(test_logger.handlers) == 1

        # Should not log replacement message
        assert "Replaced" not in caplog.text
