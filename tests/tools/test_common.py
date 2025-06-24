import pytest
from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    INPUT_DATA_TRUNCATION_LIMIT,
    LOG_DATA_TRUNCATION_LIMIT,
)
from blockscout_mcp_server.tools.common import (
    InvalidCursorError,
    _process_and_truncate_log_items,
    _recursively_truncate_and_flag_long_strings,
    decode_cursor,
    encode_cursor,
)


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

    mock_ctx.report_progress.assert_called_once_with(progress=progress, total=total, message=message)
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


def test_process_and_truncate_log_items_decoded_truncation_only():
    """Verify truncation occurs within the decoded field even without data."""
    long_value = "a" * (INPUT_DATA_TRUNCATION_LIMIT + 1)
    items = [{"decoded": {"parameters": [{"name": "foo", "value": long_value}]}}]

    processed, truncated = _process_and_truncate_log_items(items)

    assert truncated is True
    processed_value = processed[0]["decoded"]["parameters"][0]["value"]
    assert processed_value["value_truncated"] is True
    assert len(processed_value["value_sample"]) == INPUT_DATA_TRUNCATION_LIMIT


def test_process_and_truncate_log_items_short_data_long_decoded():
    """Verify long decoded value triggers truncation when data is short."""
    long_value = "b" * (INPUT_DATA_TRUNCATION_LIMIT + 1)
    items = [
        {
            "data": "0xdeadbeef",
            "decoded": {"parameters": [{"name": "bar", "value": long_value}]},
        }
    ]

    processed, truncated = _process_and_truncate_log_items(items)

    assert truncated is True
    processed_value = processed[0]["decoded"]["parameters"][0]["value"]
    assert processed_value["value_truncated"] is True
    assert processed[0].get("data_truncated") is None


def test_process_and_truncate_log_items_data_and_decoded_truncated():
    """Verify truncation occurs on both data and decoded fields."""
    long_data = "0x" + "f" * LOG_DATA_TRUNCATION_LIMIT
    long_value = "c" * (INPUT_DATA_TRUNCATION_LIMIT + 1)
    items = [
        {
            "data": long_data,
            "decoded": {"parameters": [{"name": "baz", "value": long_value}]},
        }
    ]

    processed, truncated = _process_and_truncate_log_items(items)

    assert truncated is True
    assert processed[0]["data_truncated"] is True
    processed_value = processed[0]["decoded"]["parameters"][0]["value"]
    assert processed_value["value_truncated"] is True


def test_process_and_truncate_log_items_no_decoded_field():
    """Verify items without a 'decoded' field are handled gracefully."""
    items = [{"data": "0x1234"}]
    processed, truncated = _process_and_truncate_log_items(items)

    assert truncated is False
    assert processed == items


def test_recursively_truncate_handles_simple_string():
    """Verify truncation of a simple long string."""
    long_string = "a" * (INPUT_DATA_TRUNCATION_LIMIT + 1)
    processed, truncated = _recursively_truncate_and_flag_long_strings(long_string)
    assert truncated is True
    assert processed == {
        "value_sample": "a" * INPUT_DATA_TRUNCATION_LIMIT,
        "value_truncated": True,
    }


def test_recursively_truncate_handles_short_string():
    """Verify no change for a short string."""
    short_string = "hello"
    processed, truncated = _recursively_truncate_and_flag_long_strings(short_string)
    assert truncated is False
    assert processed == short_string


def test_recursively_truncate_handles_nested_list():
    """Verify truncation within a nested list."""
    long_string = "a" * (INPUT_DATA_TRUNCATION_LIMIT + 1)
    data = ["short", ["nested_short", long_string]]
    processed, truncated = _recursively_truncate_and_flag_long_strings(data)
    assert truncated is True
    assert processed[0] == "short"
    assert processed[1][0] == "nested_short"
    assert processed[1][1]["value_truncated"] is True


def test_recursively_truncate_handles_dict():
    """Verify truncation within a dictionary's values."""
    long_string = "a" * (INPUT_DATA_TRUNCATION_LIMIT + 1)
    data = {"key1": "short", "key2": long_string}
    processed, truncated = _recursively_truncate_and_flag_long_strings(data)
    assert truncated is True
    assert processed["key1"] == "short"
    assert processed["key2"]["value_truncated"] is True


def test_recursively_truncate_no_truncation_mixed_types():
    """Verify no changes when no string is too long."""
    data = ["string", 123, True, None, {"key": "value"}]
    original_data = list(data)
    processed, truncated = _recursively_truncate_and_flag_long_strings(data)
    assert truncated is False
    assert processed == original_data
