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
    from blockscout_mcp_server.models import ChainIdGuidance

    chain_id_guidance = ChainIdGuidance(
        rules="Chain ID rule",
        recommended_chains=[ChainInfo(name="TestChain", chain_id="123")],
    )
    instructions_data = InstructionsData(
        version="1.0.0",
        error_handling_rules="Error rule",
        chain_id_guidance=chain_id_guidance,
        pagination_rules="Pagination rule",
        time_based_query_rules="Time rule",
        block_time_estimation_rules="Block rule",
        efficiency_optimization_rules="Efficiency rule",
    )
    response = ToolResponse[InstructionsData](data=instructions_data)
    assert response.data.version == "1.0.0"
    assert response.data.chain_id_guidance.recommended_chains[0].name == "TestChain"


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


def test_chain_id_guidance():
    """Test ChainIdGuidance model."""
    from blockscout_mcp_server.models import ChainIdGuidance

    chains = [ChainInfo(name="Ethereum", chain_id="1"), ChainInfo(name="Base", chain_id="8453")]
    guidance = ChainIdGuidance(rules="Chain ID rules here", recommended_chains=chains)
    assert guidance.rules == "Chain ID rules here"
    assert len(guidance.recommended_chains) == 2
    assert guidance.recommended_chains[0].name == "Ethereum"
    assert guidance.recommended_chains[1].chain_id == "8453"


def test_instructions_data():
    """Test InstructionsData model."""
    from blockscout_mcp_server.models import ChainIdGuidance

    chains = [ChainInfo(name="Ethereum", chain_id="1"), ChainInfo(name="Polygon", chain_id="137")]
    chain_id_guidance = ChainIdGuidance(rules="Chain rules", recommended_chains=chains)
    instructions = InstructionsData(
        version="2.0.0",
        error_handling_rules="Error rules",
        chain_id_guidance=chain_id_guidance,
        pagination_rules="Pagination rules",
        time_based_query_rules="Time rules",
        block_time_estimation_rules="Block rules",
        efficiency_optimization_rules="Efficiency rules",
    )
    assert instructions.version == "2.0.0"
    assert instructions.error_handling_rules == "Error rules"
    assert instructions.chain_id_guidance.rules == "Chain rules"
    assert len(instructions.chain_id_guidance.recommended_chains) == 2
    assert instructions.chain_id_guidance.recommended_chains[0].name == "Ethereum"
    assert instructions.chain_id_guidance.recommended_chains[1].chain_id == "137"
    assert instructions.pagination_rules == "Pagination rules"
    assert instructions.time_based_query_rules == "Time rules"
    assert instructions.block_time_estimation_rules == "Block rules"
    assert instructions.efficiency_optimization_rules == "Efficiency rules"


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


def test_nft_token_instance_metadata_attributes_formats():
    """Test NftTokenInstance handles both list and dict formats for metadata_attributes."""
    from blockscout_mcp_server.models import NftTokenInstance

    # Test with list format (multiple attributes)
    instance_list = NftTokenInstance(
        id="1",
        name="Test NFT",
        metadata_attributes=[
            {"trait_type": "Body", "value": "Female"},
            {"trait_type": "Hair", "value": "Wild Blonde"},
            {"trait_type": "Eyes", "value": "Green Eye Shadow"},
        ],
    )
    assert isinstance(instance_list.metadata_attributes, list)
    assert len(instance_list.metadata_attributes) == 3
    assert instance_list.metadata_attributes[0]["trait_type"] == "Body"
    assert instance_list.metadata_attributes[0]["value"] == "Female"

    # Test with dict format (single attribute)
    instance_dict = NftTokenInstance(
        id="2", name="Test NFT 2", metadata_attributes={"trait_type": "Common", "value": "Gray"}
    )
    assert isinstance(instance_dict.metadata_attributes, dict)
    assert instance_dict.metadata_attributes["trait_type"] == "Common"
    assert instance_dict.metadata_attributes["value"] == "Gray"

    # Test with None
    instance_none = NftTokenInstance(id="3", name="Test NFT 3")
    assert instance_none.metadata_attributes is None

    # Test with empty list
    instance_empty = NftTokenInstance(id="4", name="Test NFT 4", metadata_attributes=[])
    assert isinstance(instance_empty.metadata_attributes, list)
    assert len(instance_empty.metadata_attributes) == 0


def test_nft_collection_info_handles_none_values():
    """Test NftCollectionInfo handles None values for name and symbol."""
    from blockscout_mcp_server.models import NftCollectionInfo

    # Test with None name and symbol (real-world scenario from API)
    collection_with_nones = NftCollectionInfo(
        type="ERC-721", address="0x123abc", name=None, symbol=None, holders_count=10, total_supply=100
    )
    assert collection_with_nones.name is None
    assert collection_with_nones.symbol is None
    assert collection_with_nones.type == "ERC-721"
    assert collection_with_nones.address == "0x123abc"

    # Test with valid name and symbol
    collection_with_values = NftCollectionInfo(
        type="ERC-721", address="0x456def", name="Test Collection", symbol="TEST", holders_count=20, total_supply=200
    )
    assert collection_with_values.name == "Test Collection"
    assert collection_with_values.symbol == "TEST"


def test_build_tool_response_with_pagination_instructions():
    """Test that build_tool_response automatically adds pagination instructions."""
    from blockscout_mcp_server.tools.common import build_tool_response

    # Create pagination info
    pagination = PaginationInfo(
        next_call=NextCallInfo(
            tool_name="get_tokens_by_address", params={"chain_id": "1", "address": "0x123", "cursor": "next_page_token"}
        )
    )

    # Test with existing instructions
    response = build_tool_response(
        data="test_data",
        instructions=["Existing instruction"],
        pagination=pagination,
    )

    # Verify pagination instructions were added
    assert response.instructions is not None
    assert len(response.instructions) == 3  # 1 existing + 2 pagination instructions
    assert response.instructions[0] == "Existing instruction"
    assert "⚠️ MORE DATA AVAILABLE" in response.instructions[1]
    assert "Use pagination.next_call to get the next page" in response.instructions[1]
    assert "Continue calling subsequent pages" in response.instructions[2]

    # Test with no existing instructions
    response_no_existing = build_tool_response(
        data="test_data",
        pagination=pagination,
    )

    # Verify pagination instructions were added even without existing instructions
    assert response_no_existing.instructions is not None
    assert len(response_no_existing.instructions) == 2  # Only pagination instructions
    assert "⚠️ MORE DATA AVAILABLE" in response_no_existing.instructions[0]

    # Test without pagination and no instructions (should return None)
    response_no_pagination = build_tool_response(
        data="test_data",
    )

    assert response_no_pagination.instructions is None

    # Test without pagination but with empty instructions (should return empty list)
    response_empty_instructions = build_tool_response(
        data="test_data",
        instructions=[],
    )

    assert response_empty_instructions.instructions == []
