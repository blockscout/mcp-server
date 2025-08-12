import json
from typing import Annotated, Any

from eth_utils import decode_hex, to_checksum_address
from mcp.server.fastmcp import Context
from pydantic import Field
from web3.exceptions import ContractLogicError
from web3.utils.abi import check_if_arguments_can_be_encoded

from blockscout_mcp_server.models import ContractAbiData, ContractReadData, ToolResponse
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.web3_pool import WEB3_POOL

# The contracts sources are not returned by MCP tools as they consume too much context.
# More elegant solution needs to be found.


@log_tool_invocation
async def get_contract_abi(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Smart contract address")],
    ctx: Context,
) -> ToolResponse[ContractAbiData]:
    """
    Get smart contract ABI (Application Binary Interface).
    An ABI defines all functions, events, their parameters, and return types. The ABI is required to format function calls or interpret contract data.
    """  # noqa: E501
    api_path = f"/api/v2/smart-contracts/{address}"

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch contract ABI for {address} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Resolved Blockscout instance URL. Fetching contract ABI...",
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Successfully fetched contract ABI.",
    )

    # Extract the ABI from the API response as it is
    abi_data = ContractAbiData(abi=response_data.get("abi"))

    return build_tool_response(data=abi_data)


def _convert_json_args(obj: Any) -> Any:
    """
    Convert JSON-like arguments to proper Python types with deep recursion.

    - Recurses into lists and dicts
    - Attempts to apply EIP-55 checksum to address-like strings
    - Hex strings (0x...) remain as strings if not addresses
    - Numeric strings become integers
    - Other strings remain as strings
    """
    if isinstance(obj, list):
        return [_convert_json_args(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _convert_json_args(v) for k, v in obj.items()}
    if isinstance(obj, str):
        try:
            return to_checksum_address(obj)
        except Exception:
            pass
        if obj.startswith(("0x", "0X")):
            return obj
        if obj.isdigit():
            return int(obj)
        return obj
    return obj


@log_tool_invocation
async def read_contract(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Smart contract address")],
    abi: Annotated[
        dict[str, Any],
        Field(
            description=(
                "The JSON ABI for the specific function being called. This should be "
                "a dictionary that defines the function's name, inputs, and outputs. "
                "The function ABI can be obtained using the `get_contract_abi` tool."
            )
        ),
    ],
    function_name: Annotated[
        str,
        Field(
            description=(
                "The symbolic name of the function to be called. This must match the `name` field in the provided ABI."
            )
        ),
    ],
    args: Annotated[
        list[Any] | None,
        Field(
            description=(
                "A JSON array of arguments (not a string). "
                'Example: ["0xabc..."] is correct; "[\\"0xabc...\\"]" is incorrect. '
                "Order and types must match ABI inputs. Addresses: use 0x-prefixed strings; "
                "Numbers: use integers (not quoted); Bytes: keep as 0x-hex strings. If no arguments, "
                "pass [] or omit this field."
            )
        ),
    ] = None,
    block: Annotated[
        str | int,
        Field(
            description=(
                "The block identifier to read the contract state from. Can be a block "
                "number (e.g., 19000000) or a string tag (e.g., 'latest'). Defaults to 'latest'."
            )
        ),
    ] = "latest",
    *,
    ctx: Context,
) -> ToolResponse[ContractReadData]:
    """
        Calls a smart contract function (view/pure, or non-view/pure simulated via eth_call) and returns the
        decoded result.

        This tool provides a direct way to query the state of a smart contract.

        Example:
        To check the USDT balance of an address on Ethereum Mainnet, you would use the following arguments:
    {
      "tool_name": "read_contract",
      "params": {
        "chain_id": "1",
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "abi": {
          "constant": true,
          "inputs": [{"name": "_owner", "type": "address"}],
          "name": "balanceOf",
          "outputs": [{"name": "balance", "type": "uint256"}],
          "payable": false,
          "stateMutability": "view",
          "type": "function"
        },
        "function_name": "balanceOf",
        "args": ["0xF977814e90dA44bFA03b6295A0616a897441aceC"]
      }
    }
    """
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Preparing contract call {function_name} on {address}...",
    )

    # Normalize args that might be provided as a JSON-encoded string
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                '`args` must be a JSON array (e.g., ["0x..."]). Received a string that is not valid JSON.'
            ) from exc
        if not isinstance(parsed, list):
            raise ValueError("`args` must be a JSON array, not a JSON object or scalar.")
        args = parsed

    py_args = _convert_json_args(args or [])

    # Normalize block if it is a decimal string
    if isinstance(block, str) and block.isdigit():
        block = int(block)

    def _for_check(a: Any) -> Any:
        if isinstance(a, list):
            return [_for_check(i) for i in a]
        if isinstance(a, str) and a.startswith(("0x", "0X")) and len(a) != 42:
            return decode_hex(a)
        return a

    check_args = [_for_check(a) for a in py_args]
    if not check_if_arguments_can_be_encoded(abi, *check_args):
        raise ValueError(f"Arguments {py_args} cannot be encoded for function '{function_name}'")
    w3 = await WEB3_POOL.get(chain_id)
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Connected. Executing function call...",
    )
    contract = w3.eth.contract(address=to_checksum_address(address), abi=[abi])
    try:
        fn = contract.get_function_by_name(function_name)
    except ValueError as e:
        raise ValueError(f"Function name '{function_name}' is not found in provided ABI") from e
    try:
        result = await fn(*py_args).call(block_identifier=block)
    except ContractLogicError as e:
        raise RuntimeError(f"Contract call failed: {e}") from e
    except Exception as e:  # noqa: BLE001
        # Surface unexpected errors with context to the caller
        raise RuntimeError(f"Contract call errored: {type(e).__name__}: {e}") from e
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Contract call successful.",
    )
    return build_tool_response(data=ContractReadData(result=result))
