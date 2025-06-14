import pytest

from blockscout_mcp_server.tools.transaction_tools import _transform_transaction_info


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

    expected = {"from": "0xfrom", "to": None, "status": "pending"}
    assert _transform_transaction_info(data) == expected


def test_transform_no_token_transfers_key():
    data = {
        "hash": "0x3",
        "from": {"hash": "0xfrom"},
        "to": {"hash": "0xto"},
        "status": "ok",
    }

    expected = {"from": "0xfrom", "to": "0xto", "status": "ok"}
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
        "token_transfers": [
            {"from": {}, "to": {"hash": "0xy"}}
        ],
        "status": "ok",
    }

    expected = {
        "from": None,
        "to": "0xto",
        "token_transfers": [{"from": None, "to": "0xy"}],
        "status": "ok",
    }

    assert _transform_transaction_info(data) == expected
