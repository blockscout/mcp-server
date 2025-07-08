from blockscout_mcp_server.tools.transaction_tools import (
    _transform_advanced_filter_item,
    _transform_transaction_info,
)


def test_transform_standard_response():
    data = {
        "hash": "0x1",
        "from": {"hash": "0xfrom"},
        "to": {"hash": "0xto"},
        "token_transfers": [
            {
                "block_hash": "0xblock",
                "block_number": 1,
                "transaction_hash": "0x1",
                "timestamp": "2024-01-01T00:00:00Z",
                "from": {"hash": "0xA"},
                "to": {"hash": "0xB"},
                "other": 1,
            }
        ],
        "status": "ok",
    }

    expected = {
        "from": "0xfrom",
        "to": "0xto",
        "token_transfers": [
            {
                "from": "0xA",
                "to": "0xB",
                "other": 1,
            }
        ],
        "status": "ok",
    }

    assert _transform_transaction_info(data) == expected


def test_transform_contract_creation():
    data = {
        "hash": "0x2",
        "from": {"hash": "0xfrom"},
        "to": None,
        "status": "pending",
    }

    expected = {"from": "0xfrom", "to": None, "status": "pending", "token_transfers": []}
    assert _transform_transaction_info(data) == expected


def test_transform_no_token_transfers_key():
    data = {
        "hash": "0x3",
        "from": {"hash": "0xfrom"},
        "to": {"hash": "0xto"},
        "status": "ok",
    }

    expected = {"from": "0xfrom", "to": "0xto", "status": "ok", "token_transfers": []}
    assert _transform_transaction_info(data) == expected


def test_transform_empty_token_transfers():
    data = {
        "hash": "0x4",
        "from": {"hash": "0xfrom"},
        "to": {"hash": "0xto"},
        "token_transfers": [],
        "status": "ok",
    }

    expected = {"from": "0xfrom", "to": "0xto", "token_transfers": [], "status": "ok"}
    assert _transform_transaction_info(data) == expected


def test_transform_missing_hash_keys():
    data = {
        "hash": "0x5",
        "from": {},
        "to": {"hash": "0xto"},
        "token_transfers": [{"from": {}, "to": {"hash": "0xy"}}],
        "status": "ok",
    }

    expected = {
        "from": None,
        "to": "0xto",
        "token_transfers": [{"from": None, "to": "0xy"}],
        "status": "ok",
    }

    assert _transform_transaction_info(data) == expected


def test_transform_transaction_item():
    """Test transformation for a typical transaction item."""
    raw_item = {
        "from": {"hash": "0xfrom_hash"},
        "to": {"hash": "0xto_hash"},
        "token": "should be removed",
        "total": "should be removed",
        "value": "should be kept",
    }
    fields_to_remove = ["token", "total"]

    expected = {
        "from": "0xfrom_hash",
        "to": "0xto_hash",
        "value": "should be kept",
    }

    assert _transform_advanced_filter_item(raw_item, fields_to_remove) == expected


def test_transform_token_transfer_item():
    """Test transformation for a typical token transfer item."""
    raw_item = {
        "from": {"hash": "0xfrom_hash"},
        "to": {"hash": "0xto_hash"},
        "token": "should be kept",
        "total": "should be kept",
        "value": "should be removed",
        "internal_transaction_index": "should be removed",
    }
    fields_to_remove = ["value", "internal_transaction_index"]

    expected = {
        "from": "0xfrom_hash",
        "to": "0xto_hash",
        "token": "should be kept",
        "total": "should be kept",
    }

    assert _transform_advanced_filter_item(raw_item, fields_to_remove) == expected


def test_transform_item_with_missing_keys():
    """Test that the helper handles items with missing 'from' or 'to' objects."""
    raw_item = {
        "from": {"hash": "0xfrom_hash"},
        "to": None,
        "value": "should be removed",
    }
    fields_to_remove = ["value"]

    expected = {
        "from": "0xfrom_hash",
        "to": None,
    }

    assert _transform_advanced_filter_item(raw_item, fields_to_remove) == expected


def test_transformation_preserves_unknown_fields():
    """
    Test that transformation preserves fields not in the removal list.
    """
    # ARRANGE
    item_with_extra_fields = {
        "type": "call",
        "hash": "0x1",
        "from": {"hash": "0xfrom"},
        "to": {"hash": "0xto"},
        "value": "1000",
        "gas_used": "21000",
        "custom_field": "should_be_kept",
        "token": "should_be_removed",
        "timestamp": "2024-01-01T00:00:00Z",
    }
    fields_to_remove = ["token"]

    # ACT
    transformed = _transform_advanced_filter_item(item_with_extra_fields, fields_to_remove)

    # ASSERT
    # Standard transformations applied
    assert transformed["from"] == "0xfrom"
    assert transformed["to"] == "0xto"

    # Specified field removed
    assert "token" not in transformed

    # Other fields preserved
    assert transformed["type"] == "call"
    assert transformed["hash"] == "0x1"
    assert transformed["value"] == "1000"
    assert transformed["gas_used"] == "21000"
    assert transformed["custom_field"] == "should_be_kept"
    assert transformed["timestamp"] == "2024-01-01T00:00:00Z"
