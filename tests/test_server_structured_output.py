# SPDX-License-Identifier: LicenseRef-Blockscout
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_with_content_text():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool() -> ToolResponse[dict]:
        """doc"""
        return ToolResponse(data={"a": 1}, content_text="hello")

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped()

    expected_structured = {
        "data": {"a": 1},
        "data_description": None,
        "notes": None,
        "instructions": None,
        "pagination": None,
    }
    assert json.loads(result.content[0].text) == expected_structured
    assert result.structuredContent == expected_structured


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_uses_aliases_for_nested_models():
    from blockscout_mcp_server.models import TokenTransfer, ToolResponse, TransactionInfoData
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool() -> ToolResponse[TransactionInfoData]:
        return ToolResponse(
            data=TransactionInfoData(
                **{
                    "from": "0xfrom",
                    "to": "0xto",
                    "token_transfers": [
                        TokenTransfer(**{"from": "0xa", "to": "0xb", "type": "transfer", "token": None})
                    ],
                }
            )
        )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped()

    transfer = result.structuredContent["data"]["token_transfers"][0]
    assert transfer["from"] == "0xa"
    assert transfer["to"] == "0xb"
    assert transfer["type"] == "transfer"
    assert "from_address" not in transfer
    assert "to_address" not in transfer
    assert "transfer_type" not in transfer

    validated = ToolResponse[TransactionInfoData].model_validate(result.structuredContent)
    assert validated.data.token_transfers[0].from_address == "0xa"


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_fallback_and_metadata():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool() -> ToolResponse[dict]:
        """wrapped doc"""
        return ToolResponse(data={"a": 1})

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped()

    assert json.loads(result.content[0].text) == result.structuredContent
    assert "content_text" not in result.structuredContent
    assert wrapped.__name__ == _tool.__name__
    assert wrapped.__doc__ == _tool.__doc__
    assert wrapped.__annotations__ == _tool.__annotations__


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_openai_client_uses_summary_content():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1}, content_text="hello")

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"openai/userAgent": "ChatGPT/1.0"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert result.content[0].text == "hello"
    assert result.structuredContent["data"] == {"a": 1}


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_non_openai_client_uses_json_content():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1}, content_text="hello")

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"someOther/field": "value"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_non_openai_client_preserves_unicode_in_json_content():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"label": "привіт 👋"}, content_text="hello")

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"someOther/field": "value"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert "привіт" in result.content[0].text
    assert "\\u043f" not in result.content[0].text
    assert json.loads(result.content[0].text) == result.structuredContent


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_openai_client_without_content_text_uses_fallback():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1})

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"openai/userAgent": "ChatGPT/1.0"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    result = await wrapped(ctx=ctx)

    assert result.content[0].text == "Tool executed successfully."


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_structured_content_same_for_all_clients():
    from blockscout_mcp_server.models import ToolResponse
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output

    async def _tool(**kwargs) -> ToolResponse[dict]:
        return ToolResponse(data={"a": 1}, content_text="hello")

    openai_ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"openai/userAgent": "ChatGPT/1.0"}, request=SimpleNamespace(headers={})),
    )
    other_ctx = SimpleNamespace(
        request_context=SimpleNamespace(meta={"someOther/field": "value"}, request=SimpleNamespace(headers={})),
    )

    wrapped = _wrap_tool_for_structured_output(_tool)
    openai_result = await wrapped(ctx=openai_ctx)
    other_result = await wrapped(ctx=other_ctx)

    assert openai_result.structuredContent == other_result.structuredContent


@pytest.mark.asyncio
async def test_wrap_tool_for_structured_output_normalizes_bytes_from_read_contract(mock_ctx):
    """Cross-layer regression test for issue #428 at the MCP transport boundary.

    Wraps the *real* `read_contract` tool (not a dummy) with `_wrap_tool_for_structured_output`
    and drives a mocked Web3 call that returns a raw, non-UTF-8 `bytes32` value — the exact shape
    that crashed before the fix. Before the fix, this test failed with a `UnicodeDecodeError` at
    the `model_dump(mode="json")` call inside the wrapper; after the fix it passes. A
    dummy/mocked tool that already returns a normalized `0x`-hex string would pass on the buggy
    code too, so such a test could never serve as regression evidence for this fix.
    """
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output
    from blockscout_mcp_server.tools.contract.read_contract import read_contract

    non_utf8_bytes32 = bytes([0x8E]) + bytes(31)
    expected_hex = "0x8e" + "00" * 31

    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=non_utf8_bytes32)
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock

    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    wrapped = _wrap_tool_for_structured_output(read_contract)

    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        result = await wrapped(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi=abi,
            function_name="foo",
            ctx=mock_ctx,
        )

    assert result.structuredContent["data"]["result"] == expected_hex
    assert json.loads(result.content[0].text)["data"]["result"] == expected_hex
