from unittest.mock import patch

import httpx
import pytest
from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    INPUT_DATA_TRUNCATION_LIMIT,
    LOG_DATA_TRUNCATION_LIMIT,
)
from blockscout_mcp_server.models import NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.tools.common import (
    InvalidCursorError,
    _process_and_truncate_log_items,
    _recursively_truncate_and_flag_long_strings,
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    decode_cursor,
    encode_cursor,
    make_blockscout_request,
)


class MockAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.request_params: dict | None = None
        self.request_url: str | None = None

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, params: dict | None = None) -> httpx.Response:
        self.request_url = url
        self.request_params = params
        return self._response


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


def test_build_tool_response():
    """Test the build_tool_response helper function."""
    # Test with only data
    response1 = build_tool_response(data="test_data")
    assert isinstance(response1, ToolResponse)
    assert response1.data == "test_data"
    assert response1.notes is None

    # Test with all fields
    pagination = PaginationInfo(next_call=NextCallInfo(tool_name="test_tool", params={"cursor": "xyz"}))
    response2 = build_tool_response(
        data=[1, 2, 3],
        data_description=["A list of numbers."],
        notes=["This is a note."],
        instructions=["Do something else."],
        pagination=pagination,
    )
    assert response2.data == [1, 2, 3]
    assert response2.notes == ["This is a note."]
    assert response2.pagination.next_call.params["cursor"] == "xyz"


def test_build_tool_response_with_empty_lists():
    """Test build_tool_response with empty lists."""
    response = build_tool_response(
        data={"key": "value"},
        data_description=[],
        notes=[],
        instructions=[],
    )
    assert response.data_description == []
    assert response.notes == []
    assert response.instructions == []
    assert response.pagination is None


def test_build_tool_response_with_none_values():
    """Test build_tool_response with explicit None values."""
    response = build_tool_response(
        data="test",
        data_description=None,
        notes=None,
        instructions=None,
        pagination=None,
    )
    assert response.data == "test"
    assert response.data_description is None
    assert response.notes is None
    assert response.instructions is None
    assert response.pagination is None


def test_build_tool_response_complex_data():
    """Test build_tool_response with complex data structures."""
    complex_data = {
        "transactions": [
            {"hash": "0x123", "value": "1000000000000000000"},
            {"hash": "0x456", "value": "2000000000000000000"},
        ],
        "total_count": 150,
        "page_info": {"has_next": True, "cursor": "next_page"},
    }

    pagination = PaginationInfo(
        next_call=NextCallInfo(tool_name="get_transactions", params={"address": "0xabc", "cursor": "next_page"})
    )

    response = build_tool_response(
        data=complex_data,
        data_description=[
            "Array of transaction objects with hash and value fields.",
            "Value is in wei (smallest unit of ETH).",
        ],
        notes=["Data may be delayed by up to 30 seconds."],
        instructions=["Use the pagination cursor to get more results."],
        pagination=pagination,
    )

    assert response.data["total_count"] == 150
    assert len(response.data["transactions"]) == 2
    assert response.data_description[0].startswith("Array of transaction")
    assert response.notes[0] == "Data may be delayed by up to 30 seconds."
    assert response.instructions[0] == "Use the pagination cursor to get more results."
    assert response.pagination.next_call.tool_name == "get_transactions"
    assert response.pagination.next_call.params["cursor"] == "next_page"


def test_apply_cursor_to_params_success():
    """Verify the helper correctly updates params when given a valid cursor."""
    params = {"initial": "value"}
    decoded = {"page": 2, "offset": 50}
    cursor_str = "valid_cursor"

    with patch("blockscout_mcp_server.tools.common.decode_cursor") as mock_decode:
        mock_decode.return_value = decoded
        apply_cursor_to_params(cursor_str, params)
        mock_decode.assert_called_once_with(cursor_str)

    assert params == {"initial": "value", "page": 2, "offset": 50}


def test_apply_cursor_to_params_none_cursor():
    """Verify the helper leaves params unchanged when cursor is None."""
    params = {"initial": "value"}
    original = params.copy()
    apply_cursor_to_params(None, params)
    assert params == original


def test_apply_cursor_to_params_invalid_cursor_raises_value_error():
    """Verify a ValueError is raised when decode_cursor fails."""
    params = {}
    with patch("blockscout_mcp_server.tools.common.decode_cursor") as mock_decode:
        mock_decode.side_effect = InvalidCursorError
        with pytest.raises(ValueError, match="Invalid or expired pagination cursor"):
            apply_cursor_to_params("invalid", params)


def test_create_items_pagination_with_more_items():
    """Verify the helper slices the list and creates a pagination object."""
    items = [{"index": i} for i in range(20)]
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"index": item["index"]},
    )

    assert len(sliced) == page_size
    assert sliced[0]["index"] == 0
    assert sliced[-1]["index"] == page_size - 1
    assert pagination is not None
    assert pagination.next_call.tool_name == "test_tool"
    decoded_cursor = decode_cursor(pagination.next_call.params["cursor"])
    assert decoded_cursor == {"index": page_size - 1}


def test_create_items_pagination_with_fewer_items():
    """Verify the helper does nothing when items are below the page size."""
    items = [{"index": i} for i in range(5)]
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"index": item["index"]},
    )

    assert sliced == items
    assert pagination is None


def test_create_items_pagination_force_pagination_with_fewer_items():
    """Verify force_pagination=True creates pagination even when items are below page size."""
    items = [{"index": i} for i in range(5)]
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"index": item["index"]},
        force_pagination=True,
    )

    assert sliced == items  # All items should be returned
    assert pagination is not None  # Pagination should be created
    assert pagination.next_call.tool_name == "test_tool"
    decoded_cursor = decode_cursor(pagination.next_call.params["cursor"])
    assert decoded_cursor == {"index": 4}  # Last item index


def test_create_items_pagination_force_pagination_with_empty_items():
    """Verify force_pagination=True handles empty items list gracefully."""
    items = []
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"index": item["index"]},
        force_pagination=True,
    )

    assert sliced == []
    assert pagination is None  # No pagination when no items


def test_create_items_pagination_force_pagination_with_more_items():
    """Verify force_pagination=True behaves normally when items exceed page size."""
    items = [{"index": i} for i in range(20)]
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"index": item["index"]},
        force_pagination=True,
    )

    assert len(sliced) == page_size
    assert sliced[0]["index"] == 0
    assert sliced[-1]["index"] == page_size - 1
    assert pagination is not None
    assert pagination.next_call.tool_name == "test_tool"
    decoded_cursor = decode_cursor(pagination.next_call.params["cursor"])
    assert decoded_cursor == {"index": page_size - 1}  # Same behavior as normal case


def test_create_items_pagination_force_pagination_cursor_generation():
    """Verify force_pagination=True uses the last item for cursor generation."""
    items = [{"block_number": 100, "index": 1}, {"block_number": 200, "index": 2}]
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"block_number": item["block_number"], "index": item["index"]},
        force_pagination=True,
    )

    assert sliced == items
    assert pagination is not None
    decoded_cursor = decode_cursor(pagination.next_call.params["cursor"])
    assert decoded_cursor == {"block_number": 200, "index": 2}  # Last item's data


def test_create_items_pagination_normal_cursor_generation():
    """Verify normal pagination uses the item at page_size-1 for cursor generation."""
    items = [{"block_number": 100 + i, "index": i} for i in range(15)]
    page_size = 10

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params={"chain_id": "1"},
        cursor_extractor=lambda item: {"block_number": item["block_number"], "index": item["index"]},
    )

    assert len(sliced) == page_size
    assert pagination is not None
    decoded_cursor = decode_cursor(pagination.next_call.params["cursor"])
    # Should use items[page_size - 1] = items[9] = {"block_number": 109, "index": 9}
    assert decoded_cursor == {"block_number": 109, "index": 9}


def test_create_items_pagination_preserves_base_params():
    """Verify pagination preserves base parameters and adds cursor."""
    items = [{"index": i} for i in range(5)]
    page_size = 10
    base_params = {"chain_id": "1", "address": "0x123", "other": "value"}

    sliced, pagination = create_items_pagination(
        items=items,
        page_size=page_size,
        tool_name="test_tool",
        next_call_base_params=base_params,
        cursor_extractor=lambda item: {"index": item["index"]},
        force_pagination=True,
    )

    assert pagination is not None
    params = pagination.next_call.params
    assert params["chain_id"] == "1"
    assert params["address"] == "0x123"
    assert params["other"] == "value"
    assert "cursor" in params
    decoded_cursor = decode_cursor(params["cursor"])
    assert decoded_cursor == {"index": 4}


def test_extract_log_cursor_params():
    """Verify the log cursor extractor works correctly."""
    from blockscout_mcp_server.tools.common import extract_log_cursor_params

    complete_item = {"block_number": 123, "index": 7, "data": "0x"}
    assert extract_log_cursor_params(complete_item) == {"block_number": 123, "index": 7}

    missing_fields_item = {"data": "0xdead"}
    assert extract_log_cursor_params(missing_fields_item) == {"block_number": None, "index": None}

    assert extract_log_cursor_params({}) == {"block_number": None, "index": None}


def test_extract_advanced_filters_cursor_params():
    """Verify the advanced filters cursor extractor works correctly."""
    from blockscout_mcp_server.tools.common import (
        extract_advanced_filters_cursor_params,
    )

    item = {
        "block_number": 100,
        "transaction_index": 5,
        "internal_transaction_index": 2,
        "token_transfer_batch_index": None,
        "token_transfer_index": 1,
        "other_field": "ignore",
    }

    expected_params = {
        "block_number": 100,
        "transaction_index": 5,
        "internal_transaction_index": 2,
        "token_transfer_batch_index": None,
        "token_transfer_index": 1,
    }

    assert extract_advanced_filters_cursor_params(item) == expected_params

    item_missing = {"block_number": 200}
    expected_missing = {
        "block_number": 200,
        "transaction_index": None,
        "internal_transaction_index": None,
        "token_transfer_batch_index": None,
        "token_transfer_index": None,
    }

    assert extract_advanced_filters_cursor_params(item_missing) == expected_missing


@pytest.mark.asyncio
async def test_make_blockscout_request_json_api_error_sort():
    """Verify JSON:API errors include title, detail, and pointer."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(
        422,
        json={
            "errors": [
                {
                    "title": "Invalid value",
                    "source": {"pointer": "/sort"},
                    "detail": "Unexpected field: sort",
                }
            ]
        },
        request=request,
    )

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert "422 Unprocessable Entity - Details: Invalid value: Unexpected field: sort (at /sort)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_json_api_error_address_format():
    """Verify JSON:API errors include pointer details for address fields."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(
        422,
        json={
            "errors": [
                {
                    "title": "Invalid value",
                    "source": {"pointer": "/address_hash_param"},
                    "detail": "Invalid format",
                }
            ]
        },
        request=request,
    )

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert "Details: Invalid value: Invalid format (at /address_hash_param)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_simple_json_error_message():
    """Verify message fields are surfaced for generic JSON errors."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(400, json={"message": "Invalid chain ID"}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert "Details: Invalid chain ID" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_error_field_fallback():
    """Verify error fields are surfaced when provided."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(400, json={"error": "Some error text"}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert "Details: Some error text" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_errors_string_items():
    """Verify string items in errors array are included."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(422, json={"errors": ["Simple error message"]}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert "Details: Simple error message" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_errors_title_no_detail():
    """Verify errors with title but empty detail are formatted consistently."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(
        422,
        json={
            "errors": [
                {
                    "title": "Invalid value",
                    "source": {"pointer": "/sort"},
                    "detail": "",
                }
            ]
        },
        request=request,
    )

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert "Details: Invalid value (at /sort)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_multiple_errors_joined():
    """Verify multiple errors are joined with semicolons."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(
        422,
        json={
            "errors": [
                {"title": "First error", "detail": "First detail", "source": {"pointer": "/first"}},
                {"title": "Second error", "detail": "Second detail"},
            ]
        },
        request=request,
    )

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    message = str(exc_info.value)
    assert "First error: First detail (at /first); Second error: Second detail" in message


@pytest.mark.asyncio
async def test_make_blockscout_request_empty_details_message():
    """Verify empty bodies omit the details suffix."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(422, content=b"", request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert str(exc_info.value).startswith("422 Unprocessable Entity")
    assert "Details:" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_raw_text_error_truncation():
    """Verify raw text errors are truncated to 200 characters."""
    html_body = "<html><body><h1>502 Bad Gateway</h1>" + ("a" * 250) + "</body></html>"
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(502, content=html_body.encode(), request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await make_blockscout_request("https://example.com", "/api/v2/test")

    assert html_body[:200] in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_success():
    """Verify successful responses return JSON payloads."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(200, json={"result": "success"}, request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        result = await make_blockscout_request("https://example.com", "/api/v2/test")

    assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_make_blockscout_request_returns_empty_dict_on_null_response():
    """Verify null JSON bodies return an empty dictionary."""
    request = httpx.Request("GET", "https://example.com/api/v2/test")
    response = httpx.Response(200, content=b"null", request=request)

    with patch(
        "blockscout_mcp_server.tools.common._create_httpx_client",
        return_value=MockAsyncClient(response),
    ):
        result = await make_blockscout_request("https://example.com", "/api/v2/test")

    assert result == {}
