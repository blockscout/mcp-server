import pytest
from mcp.server.fastmcp import Context
from blockscout_mcp_server.tools.common import (
    encode_cursor,
    decode_cursor,
    InvalidCursorError,
    _process_and_truncate_log_items,
)
from blockscout_mcp_server.constants import LOG_DATA_TRUNCATION_LIMIT


def test_encode_decode_roundtrip():
    """Verify that encoding and then decoding returns the original data."""
    params = {"block_number": 123, "index": 456, "items_count": 50}
    encoded = encode_cursor(params)
    decoded = decode_cursor(encoded)
    assert decoded == params


def test_encode_empty_dict():
    """Verify encoding an empty dict returns an empty string."""
    assert encode_cursor({}) == ""


def test_decode_invalid_cursor():
    """Verify decoding a malformed string raises the correct error."""
    with pytest.raises(InvalidCursorError, match="Invalid or expired cursor provided."):
        decode_cursor("this-is-not-valid-base64")


def test_decode_empty_cursor():
    """Verify decoding an empty string raises an error."""
    with pytest.raises(InvalidCursorError, match="Cursor cannot be empty."):
        decode_cursor("")


def test_decode_valid_base64_invalid_json():
    """Verify decoding valid base64 that isn't JSON raises an error."""
    invalid_json_cursor = "bm90IGpzb24="  # base64 for 'not json'
    with pytest.raises(InvalidCursorError, match="Invalid or expired cursor provided."):
        decode_cursor(invalid_json_cursor)


@pytest.mark.asyncio
async def test_report_and_log_progress(mock_ctx: Context):
    """Verify the helper calls both report_progress and info with correct args."""
    progress, total, message = 1.0, 2.0, "Step 1 Complete"

    from blockscout_mcp_server.tools.common import report_and_log_progress

    await report_and_log_progress(mock_ctx, progress, total, message)

    mock_ctx.report_progress.assert_called_once_with(
        progress=progress, total=total, message=message
    )
    expected_log_message = f"Progress: {progress}/{total} - {message}"
    mock_ctx.info.assert_called_once_with(expected_log_message)


def test_process_and_truncate_log_items_no_truncation():
    """Verify items with data under the limit are untouched."""
    items = [{"data": "0x" + "a" * 10}]
    processed, truncated = _process_and_truncate_log_items(items)
    assert not truncated
    assert processed == items
    assert "data_truncated" not in processed[0]


def test_process_and_truncate_log_items_with_truncation():
    """Verify items with data over the limit are truncated."""
    long_data = "0x" + "a" * (LOG_DATA_TRUNCATION_LIMIT)
    items = [{"data": long_data}]
    processed, truncated = _process_and_truncate_log_items(items)
    assert truncated
    assert len(processed[0]["data"]) == LOG_DATA_TRUNCATION_LIMIT
    assert processed[0]["data_truncated"] is True


def test_process_and_truncate_log_items_mixed():
    """Verify a mix of items is handled correctly."""
    items = [
        {"data": "0xshort"},
        {"data": "0x" + "a" * (LOG_DATA_TRUNCATION_LIMIT)},
    ]
    processed, truncated = _process_and_truncate_log_items(items)
    assert truncated
    assert len(processed[1]["data"]) == LOG_DATA_TRUNCATION_LIMIT
    assert processed[1]["data_truncated"] is True
    assert "data_truncated" not in processed[0]


def test_process_and_truncate_log_items_no_data_field():
    """Verify items without a 'data' field are handled gracefully."""
    items = [{"topics": ["0x123"]}]
    processed, truncated = _process_and_truncate_log_items(items)
    assert not truncated
    assert processed == items
