# SPDX-License-Identifier: LicenseRef-Blockscout
# tests/tools/contract/conftest.py
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def build_w3_mock():
    """Factory for the WEB3_POOL.get()-shaped mock chain used by read_contract tests.

    The returned callable takes the value the contract function's `.call()` should
    resolve to and, optionally, a `codec` to attach to the w3 mock. Pass a real
    codec (e.g. `Web3().codec`) in preflight-focused tests so
    `check_if_arguments_can_be_encoded` runs against genuine encoders instead of a
    truthy MagicMock attribute.
    """

    def _build(call_return_value: Any, codec: Any = None) -> MagicMock:
        fn_result = MagicMock()
        fn_result.call = AsyncMock(return_value=call_return_value)
        fn_mock = MagicMock(return_value=fn_result)
        contract_mock = MagicMock()
        contract_mock.get_function_by_name.return_value = fn_mock
        w3_mock = MagicMock()
        if codec is not None:
            w3_mock.codec = codec
        w3_mock.eth.contract.return_value = contract_mock
        return w3_mock

    return _build
