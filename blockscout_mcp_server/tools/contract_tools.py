from typing import Annotated, Any

from eth_utils import to_checksum_address
from mcp.server.fastmcp import Context
from pydantic import Field
from web3.exceptions import ContractLogicError

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


def _convert_json_args(args: list[Any]) -> list[Any]:
    out: list[Any] = []
    for a in args:
        if isinstance(a, list):
            out.append(_convert_json_args(a))
        elif isinstance(a, str):
            if a.startswith(("0x", "0X")):
                out.append(a)
            elif a.isdigit():
                out.append(int(a))
            else:
                out.append(a)
        else:
            out.append(a)
    return out


@log_tool_invocation
async def read_contract(
    chain_id: Annotated[str, Field(description="The ID of the blockchain to operate on.")],
    address: Annotated[str, Field(description="The address of the smart contract to call.")],
    abi: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "The JSON ABI for the specific function being called. This should be "
                "a list containing a single dictionary that defines the function's "
                "name, inputs, and outputs. The function ABI can be obtained using the "
                "`get_contract_abi` tool."
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
                "A list of arguments to pass to the function. The order and types must "
                "match the function's definition in the ABI. Defaults to an empty list "
                "if omitted."
            )
        ),
    ] = None,
    block: Annotated[
        str | int,
        Field(
            description=(
                "The block identifier to read the contract state from. Can be a block "
                "number (e.g., 19000000) or a string tag (e.g., 'latest', 'pending'). "
                "Defaults to 'latest'."
            )
        ),
    ] = "latest",
    *,
    ctx: Context,
) -> ToolResponse[ContractReadData]:
    """
        Calls a read-only (view/pure) function of a smart contract and returns the
        decoded result.

        This tool provides a direct way to query the state of a smart contract
        without needing to parse raw blockchain data. It is useful for tasks like
        checking balances, reading configuration values, or verifying ownership.

        Example:
        To check the USDT balance of an address on Ethereum Mainnet, you would use the following arguments:
    {
      "tool_name": "read_contract",
      "params": {
        "chain_id": "1",
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "abi": [{
          "constant": true,
          "inputs": [{"name": "_owner", "type": "address"}],
          "name": "balanceOf",
          "outputs": [{"name": "balance", "type": "uint256"}],
          "payable": false,
          "stateMutability": "view",
          "type": "function"
        }],
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
    w3 = await WEB3_POOL.get(chain_id)
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Connected. Executing function call...",
    )
    contract = w3.eth.contract(address=to_checksum_address(address), abi=abi)
    fn = contract.get_function_by_name(function_name)
    if isinstance(fn, list):
        raise ValueError(f"Function name '{function_name}' is overloaded; use get_function_by_signature(...) instead.")
    py_args = _convert_json_args(args or [])
    try:
        result = await fn(*py_args).call(block_identifier=block)
    except ContractLogicError as e:
        raise RuntimeError(f"Contract call failed: {e}") from e
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Contract call successful.",
    )
    return build_tool_response(data=ContractReadData(result=result))
