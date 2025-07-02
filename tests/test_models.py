"""Tests for the Pydantic response models."""

import json

from blockscout_mcp_server.models import (
    AddressInfoData,
    BlockInfoData,
    ChainInfo,
    DecodedInput,
    InstructionsData,
    NextCallInfo,
    NftCollectionHolding,
    PaginationInfo,
    TokenTransfer,
    ToolResponse,
    TransactionInfoData,
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
        recommended_chains=[ChainInfo(name="TestChain", chain_id="123")],
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


def test_next_call_info():
    """Test NextCallInfo model."""
    next_call_info = NextCallInfo(
        tool_name="get_address_info", params={"chain_id": "1", "address": "0x123", "cursor": "xyz"}
    )
    assert next_call_info.tool_name == "get_address_info"
    assert next_call_info.params["chain_id"] == "1"
    assert next_call_info.params["cursor"] == "xyz"


def test_pagination_info():
    """Test PaginationInfo model."""
    next_call = NextCallInfo(tool_name="test_tool", params={"param": "value"})
    pagination_info = PaginationInfo(next_call=next_call)
    assert pagination_info.next_call.tool_name == "test_tool"
    assert pagination_info.next_call.params["param"] == "value"


def test_chain_info():
    """Test ChainInfo model."""
    chain = ChainInfo(name="Ethereum", chain_id="1")
    assert chain.name == "Ethereum"
    assert chain.chain_id == "1"


def test_instructions_data():
    """Test InstructionsData model."""
    chains = [ChainInfo(name="Ethereum", chain_id="1"), ChainInfo(name="Polygon", chain_id="137")]
    instructions = InstructionsData(version="2.0.0", general_rules=["Rule 1", "Rule 2"], recommended_chains=chains)
    assert instructions.version == "2.0.0"
    assert len(instructions.general_rules) == 2
    assert len(instructions.recommended_chains) == 2
    assert instructions.recommended_chains[0].name == "Ethereum"
    assert instructions.recommended_chains[1].chain_id == "137"


def test_tool_response_serialization():
    """Test that ToolResponse serializes correctly to JSON."""
    pagination = PaginationInfo(
        next_call=NextCallInfo(tool_name="get_blocks", params={"chain_id": "1", "cursor": "next_page_token"})
    )
    response = ToolResponse[list](
        data=[{"block": 1}, {"block": 2}],
        data_description=["List of block objects"],
        notes=["Some blocks may be pending"],
        instructions=["Use cursor for next page"],
        pagination=pagination,
    )

    # Test model_dump_json
    json_str = response.model_dump_json()
    parsed = json.loads(json_str)

    assert parsed["data"] == [{"block": 1}, {"block": 2}]
    assert parsed["data_description"] == ["List of block objects"]
    assert parsed["notes"] == ["Some blocks may be pending"]
    assert parsed["instructions"] == ["Use cursor for next page"]
    assert parsed["pagination"]["next_call"]["tool_name"] == "get_blocks"
    assert parsed["pagination"]["next_call"]["params"]["cursor"] == "next_page_token"


def test_tool_response_with_none_values():
    """Test ToolResponse behavior with None values for optional fields."""
    response = ToolResponse[str](
        data="test_data", data_description=None, notes=None, instructions=None, pagination=None
    )

    assert response.data == "test_data"
    assert response.data_description is None
    assert response.notes is None
    assert response.instructions is None
    assert response.pagination is None

    # Test serialization preserves None values
    json_output = json.loads(response.model_dump_json())
    assert json_output["data_description"] is None
    assert json_output["notes"] is None
    assert json_output["instructions"] is None
    assert json_output["pagination"] is None


def test_tool_response_with_empty_lists():
    """Test ToolResponse with empty lists for optional fields."""
    response = ToolResponse[dict](data={"test": "value"}, data_description=[], notes=[], instructions=[])

    assert response.data_description == []
    assert response.notes == []
    assert response.instructions == []

    # Empty lists should serialize properly
    json_output = json.loads(response.model_dump_json())
    assert json_output["data_description"] == []
    assert json_output["notes"] == []
    assert json_output["instructions"] == []


def test_address_info_data_model():
    """Verify AddressInfoData holds basic and metadata info."""
    # Test with all fields populated
    basic = {"hash": "0xabc", "is_contract": False}
    metadata = {"tags": [{"name": "Known"}]}
    data_full = AddressInfoData(basic_info=basic, metadata=metadata)

    assert data_full.basic_info == basic
    assert data_full.metadata == metadata

    # Test with optional metadata omitted
    data_no_meta = AddressInfoData(basic_info=basic)
    assert data_no_meta.basic_info == basic
    assert data_no_meta.metadata is None, "Metadata should default to None when not provided"


def test_transaction_info_data_handles_extra_fields_recursively():
    """Verify TransactionInfoData preserves extra fields at all levels."""
    api_data = {
        "from": "0xfrom_address",
        "to": "0xto_address",
        "token_transfers": [
            {
                "from": "0xa",
                "to": "0xb",
                "token": {},
                "type": "transfer",
                "a_new_token_field": "token_extra_value",
            }
        ],
        "decoded_input": {
            "method_call": "test()",
            "method_id": "0x123",
            "parameters": [],
            "a_new_decoded_field": "decoded_extra_value",
        },
        "a_new_field_from_api": "some_value",
        "status": "ok",
    }

    model = TransactionInfoData(**api_data)

    assert model.from_address == "0xfrom_address"
    assert model.a_new_field_from_api == "some_value"
    assert model.status == "ok"

    assert isinstance(model.token_transfers[0], TokenTransfer)
    assert model.token_transfers[0].from_address == "0xa"
    assert model.token_transfers[0].transfer_type == "transfer"
    assert model.token_transfers[0].a_new_token_field == "token_extra_value"

    assert isinstance(model.decoded_input, DecodedInput)
    assert model.decoded_input.method_id == "0x123"
    assert model.decoded_input.a_new_decoded_field == "decoded_extra_value"

    dumped_model = model.model_dump(by_alias=True)
    assert dumped_model["a_new_field_from_api"] == "some_value"
    assert dumped_model["token_transfers"][0]["a_new_token_field"] == "token_extra_value"
    assert dumped_model["decoded_input"]["a_new_decoded_field"] == "decoded_extra_value"


def test_block_info_data_model():
    """Verify BlockInfoData model structure and extra field handling."""
    block_data = {
        "height": 123,
        "timestamp": "2024-01-01T00:00:00Z",
        "a_new_field_from_api": "some_value",
    }
    tx_hashes = ["0x1", "0x2"]

    # Test with all fields
    model_full = BlockInfoData(block_details=block_data, transaction_hashes=tx_hashes)
    assert model_full.block_details["height"] == 123
    assert model_full.block_details["a_new_field_from_api"] == "some_value"
    assert model_full.transaction_hashes == tx_hashes

    # Test with optional field omitted
    model_basic = BlockInfoData(block_details=block_data)
    assert model_basic.transaction_hashes is None


def test_nft_collection_holding_model():
    """Verify NftCollectionHolding model with nested structures."""

    holding_data = {
        "collection": {
            "type": "ERC-721",
            "address": "0xabc",
            "name": "Sample Collection",
            "symbol": "SAMP",
            "holders_count": 42,
            "total_supply": 1000,
        },
        "amount": "2",
        "token_instances": [
            {
                "id": "1",
                "name": "NFT #1",
                "description": "First token",
                "image_url": "https://img/1.png",
                "external_app_url": "https://example.com/1",
                "metadata_attributes": [{"trait_type": "Color", "value": "Red"}],
            },
            {"id": "2", "name": "NFT #2"},
        ],
    }

    holding = NftCollectionHolding(**holding_data)

    assert holding.collection.name == "Sample Collection"
    assert holding.collection.address == "0xabc"
    assert holding.amount == "2"
    assert len(holding.token_instances) == 2
    assert holding.token_instances[0].metadata_attributes[0]["value"] == "Red"
    assert holding.token_instances[1].name == "NFT #2"
