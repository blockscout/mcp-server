import json
from typing import Annotated, Any

from eth_utils import decode_hex, to_checksum_address
from mcp.server.fastmcp import Context
from pydantic import Field
from web3.exceptions import ContractLogicError
from web3.utils.abi import check_if_arguments_can_be_encoded

from blockscout_mcp_server.models import ContractReadData, ToolResponse
from blockscout_mcp_server.tools.common import build_tool_response, report_and_log_progress
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.web3_pool import WEB3_POOL


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
        # Robust numeric detection: support negatives and large ints
        try:
            return int(obj, 10)
        except ValueError:
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
        str,
        Field(
            description=(
                "A JSON string containing an array of arguments. "
                'Example: "["0xabc..."]" for a single address argument, or "[]" for no arguments. '
                "Order and types must match ABI inputs. Addresses: use 0x-prefixed strings; "
                'Numbers: prefer integers (not quoted); numeric strings like "1" are also '
                "accepted and coerced to integers. "
                "Bytes: keep as 0x-hex strings."
            )
        ),
    ] = "[]",
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
        "args": "[\"0xF977814e90dA44bFA03b6295A0616a897441aceC\"]"
      }
    }
    """
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Preparing contract call {function_name} on {address}...",
    )

    # Parse args from JSON string
    args_str = args.strip()
    if args_str == "":
        args_str = "[]"
    try:
        parsed = json.loads(args_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            '`args` must be a JSON array string (e.g., "["0x..."]"). Received a string that is not valid JSON.'
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(f"`args` must be a JSON array string representing a list; got {type(parsed).__name__}.")
    py_args = _convert_json_args(parsed)

    # Early arity validation for clearer feedback
    abi_inputs = abi.get("inputs", [])
    if isinstance(abi_inputs, list) and len(py_args) != len(abi_inputs):
        raise ValueError(f"Argument count mismatch: expected {len(abi_inputs)} per ABI, got {len(py_args)}.")

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
