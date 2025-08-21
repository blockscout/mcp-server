from blockscout_mcp_server.tools.common import (
    INPUT_DATA_TRUNCATION_LIMIT,
    _truncate_constructor_args,
)


def test_truncate_constructor_args_list():
    data = ["a" * (INPUT_DATA_TRUNCATION_LIMIT + 1)]
    processed, truncated = _truncate_constructor_args(data)
    assert truncated is True
    assert processed[0]["value_truncated"] is True


def test_truncate_constructor_args_dict():
    data = {"arg": "b" * (INPUT_DATA_TRUNCATION_LIMIT + 1)}
    processed, truncated = _truncate_constructor_args(data)
    assert truncated is True
    assert processed["arg"]["value_truncated"] is True
