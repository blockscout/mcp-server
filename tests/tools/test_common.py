import pytest
from mcp.server.fastmcp import Context
from blockscout_mcp_server.tools.common import encode_cursor, decode_cursor, InvalidCursorError


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
