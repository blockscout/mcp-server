"""Tests for the Pydantic response models."""

import json

from blockscout_mcp_server.models import (
    InstructionsData,
    NextCallInfo,
    PaginationInfo,
    RecommendedChain,
    ToolResponse,
)


def test_tool_response_simple_data():
    """Test ToolResponse with a simple string payload."""
    response = ToolResponse[str](data="Hello, world!")
    assert response.data == "Hello, world!"
    assert response.notes is None
    json_output = response.model_dump_json()
    assert json.loads(json_output) == {
        "data": "Hello, world!",
        "data_description": None,
        "notes": None,
        "instructions": None,
        "pagination": None,
    }


def test_tool_response_complex_data():
    """Test ToolResponse with a nested Pydantic model as data."""
    instructions_data = InstructionsData(
        version="1.0.0",
        general_rules=["Rule 1"],
        recommended_chains=[RecommendedChain(name="TestChain", chain_id=123)],
    )
    response = ToolResponse[InstructionsData](data=instructions_data)
    assert response.data.version == "1.0.0"
    assert response.data.recommended_chains[0].name == "TestChain"


def test_tool_response_with_all_fields():
    """Test ToolResponse with all optional fields populated."""
    pagination = PaginationInfo(next_call=NextCallInfo(tool_name="next_tool", params={"cursor": "abc"}))
    response = ToolResponse[dict](
        data={"key": "value"},
        data_description=["This is a dictionary."],
        notes=["Data might be incomplete."],
        instructions=["Call another tool next."],
        pagination=pagination,
    )
    assert response.notes == ["Data might be incomplete."]
    assert response.pagination.next_call.tool_name == "next_tool"
    json_output = response.model_dump_json()
    assert json.loads(json_output)["pagination"]["next_call"]["params"]["cursor"] == "abc"
