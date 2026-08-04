# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the client-disconnect logging filter in blockscout_mcp_server.logging_utils."""

import io
import logging

import anyio
import pytest

from blockscout_mcp_server.logging_utils import (
    CLIENT_DISCONNECT_LOGGER_NAME,
    CLIENT_DISCONNECT_RECORD_MESSAGE,
    ClientDisconnectFilter,
    install_client_disconnect_filter,
)

DEMOTED_MESSAGE = "Stateless session closed by client disconnect (anyio.ClosedResourceError); traceback suppressed."


def _make_record(message: str, exc_info: tuple | None) -> logging.LogRecord:
    """Build a bare LogRecord with the given message and exc_info tuple."""
    return logging.LogRecord(
        name="mcp.server.streamable_http_manager",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=None,
        exc_info=exc_info,
    )


def _exc_info_for(exception: BaseException) -> tuple:
    """Build an exc_info-shaped tuple for a given exception instance (no real traceback needed)."""
    return (type(exception), exception, None)


def _closed_resource_error() -> anyio.ClosedResourceError:
    try:
        raise anyio.ClosedResourceError()
    except anyio.ClosedResourceError as exc:
        return exc


def _nested_closed_resource_group() -> BaseExceptionGroup:
    """Build a ClosedResourceError wrapped in two nested ExceptionGroups."""
    inner = BaseExceptionGroup("inner", [_closed_resource_error()])
    outer = BaseExceptionGroup("outer", [inner])
    return outer


class TestClientDisconnectFilterMatching:
    """Tests for the matching/demotion logic of ClientDisconnectFilter."""

    def test_bare_closed_resource_error_is_demoted(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(_closed_resource_error()))
        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.DEBUG

    def test_demotion_rewrites_levelname(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(_closed_resource_error()))
        ClientDisconnectFilter().filter(record)
        assert record.levelname == "DEBUG"

    def test_demotion_clears_exc_info_exc_text_and_stack_info(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(_closed_resource_error()))
        record.exc_text = "sentinel-exc-text"
        record.stack_info = "sentinel-stack-info"

        ClientDisconnectFilter().filter(record)

        assert record.exc_info is None
        assert record.exc_text is None
        assert record.stack_info is None

    def test_demotion_replaces_message_with_exact_one_liner(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(_closed_resource_error()))
        ClientDisconnectFilter().filter(record)
        assert record.getMessage() == DEMOTED_MESSAGE

    def test_nested_exception_groups_are_demoted(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(_nested_closed_resource_group()))
        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.DEBUG
        assert record.getMessage() == DEMOTED_MESSAGE

    def test_different_message_with_matching_tree_passes_through_untouched(self):
        record = _make_record("Session abc123 crashed: boom", _exc_info_for(_closed_resource_error()))
        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.ERROR
        assert record.getMessage() == "Session abc123 crashed: boom"

    def test_group_with_unrelated_exception_passes_through_untouched(self):
        group = BaseExceptionGroup("mixed", [_closed_resource_error(), ValueError("unrelated")])
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(group))
        record.exc_text = "sentinel-exc-text"
        record.stack_info = "sentinel-stack-info"

        original = {
            "levelno": record.levelno,
            "levelname": record.levelname,
            "msg": record.msg,
            "args": record.args,
            "exc_info": record.exc_info,
            "exc_text": record.exc_text,
            "stack_info": record.stack_info,
        }

        ClientDisconnectFilter().filter(record)

        assert record.levelno == original["levelno"]
        assert record.levelname == original["levelname"]
        assert record.msg == original["msg"]
        assert record.args == original["args"]
        assert record.exc_info == original["exc_info"]
        assert record.exc_text == original["exc_text"]
        assert record.stack_info == original["stack_info"]

    def test_unrelated_exception_passes_through_untouched(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(ValueError("boom")))
        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.ERROR
        assert record.getMessage() == CLIENT_DISCONNECT_RECORD_MESSAGE

    def test_explicit_cause_chain_is_not_traversed(self):
        try:
            try:
                raise _closed_resource_error()
            except anyio.ClosedResourceError as cause:
                raise ValueError("wrapped") from cause
        except ValueError as exc:
            record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(exc))

        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.ERROR

    def test_implicit_context_chain_is_not_traversed(self):
        try:
            try:
                raise _closed_resource_error()
            except anyio.ClosedResourceError:
                raise ValueError("wrapped")
        except ValueError as exc:
            record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(exc))

        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.ERROR

    def test_record_without_exc_info_passes_through_untouched(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, None)
        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.ERROR

    def test_record_with_empty_exc_info_tuple_passes_through_untouched(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, (None, None, None))
        ClientDisconnectFilter().filter(record)
        assert record.levelno == logging.ERROR

    def test_filter_returns_true_for_matching_record(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(_closed_resource_error()))
        assert ClientDisconnectFilter().filter(record) is True

    def test_filter_returns_true_for_non_matching_record(self):
        record = _make_record(CLIENT_DISCONNECT_RECORD_MESSAGE, _exc_info_for(ValueError("boom")))
        assert ClientDisconnectFilter().filter(record) is True


class TestInstallClientDisconnectFilter:
    """Tests for the install_client_disconnect_filter installer function."""

    def test_installer_is_idempotent(self):
        logger_name = "test_install_client_disconnect_filter_idempotent"
        logger = logging.getLogger(logger_name)
        try:
            install_client_disconnect_filter(logger_name)
            install_client_disconnect_filter(logger_name)

            matching_filters = [f for f in logger.filters if isinstance(f, ClientDisconnectFilter)]
            assert len(matching_filters) == 1
        finally:
            logger.filters.clear()


class TestClientDisconnectFilterEndToEnd:
    """End-to-end visibility test: demoted record is emitted as a single DEBUG line."""

    def test_demoted_record_is_visible_as_single_debug_line(self):
        logger_name = "test_client_disconnect_filter_end_to_end"
        logger = logging.getLogger(logger_name)
        original_level = logger.level
        original_propagate = logger.propagate
        original_filters = logger.filters[:]
        original_handlers = logger.handlers[:]

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.NOTSET)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

        try:
            logger.filters.clear()
            logger.handlers.clear()
            logger.setLevel(logging.INFO)
            logger.propagate = False
            logger.addFilter(ClientDisconnectFilter())
            logger.addHandler(handler)

            try:
                raise _nested_closed_resource_group()
            except BaseExceptionGroup:
                logger.error(CLIENT_DISCONNECT_RECORD_MESSAGE, exc_info=True)

            assert stream.getvalue() == f"DEBUG - {DEMOTED_MESSAGE}\n"
        finally:
            logger.setLevel(original_level)
            logger.propagate = original_propagate
            logger.filters.clear()
            logger.filters.extend(original_filters)
            logger.handlers.clear()
            logger.handlers.extend(original_handlers)


class TestServerStartupWiring:
    """Tests that importing the server module installs the filter on the real SDK logger."""

    def test_server_import_installs_filter_exactly_once(self):
        import blockscout_mcp_server.server  # noqa: F401

        logger = logging.getLogger(CLIENT_DISCONNECT_LOGGER_NAME)
        matching_filters = [f for f in logger.filters if isinstance(f, ClientDisconnectFilter)]
        assert len(matching_filters) == 1


if __name__ == "__main__":
    pytest.main([__file__])
