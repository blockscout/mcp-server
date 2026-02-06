from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import (
    ContractMetadata,
    ContractSourceFile,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import build_tool_response, report_and_log_progress
from blockscout_mcp_server.tools.contract._shared import _fetch_and_process_contract
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
async def inspect_contract_code(
    chain_id: Annotated[str, Field(description="The ID of the blockchain.")],
    address: Annotated[str, Field(description="The address of the smart contract.")],
    file_name: Annotated[
        str | None,
        Field(
            description=(
                "The name of the source file to inspect. "
                "If omitted, returns contract metadata and the list of source files."
            ),
        ),
    ] = None,
    *,
    ctx: Context,
) -> ToolResponse[ContractMetadata | ContractSourceFile]:
    """Inspects a verified contract's source code or metadata."""
    if file_name is None:
        start_msg = f"Starting to fetch contract metadata for {address} on chain {chain_id}..."
    else:
        start_msg = f"Starting to fetch source code for '{file_name}' of contract {address} on chain {chain_id}..."
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=start_msg,
    )

    processed = await _fetch_and_process_contract(chain_id, address, ctx)
    if file_name is None:
        metadata = ContractMetadata.model_validate(processed.metadata)
        instructions = None
        notes = None
        if metadata.constructor_args_truncated:
            notes = ["Constructor arguments were truncated to limit context size."]
        if processed.source_files:
            instructions = [
                (
                    "To retrieve a specific file's contents, call this tool again with the "
                    "'file_name' argument using one of the values from 'source_code_tree_structure'."
                )
            ]
        return build_tool_response(
            data=metadata,
            instructions=instructions,
            notes=notes,
            content_text=(f"Contract {address} on chain {chain_id}: {len(processed.source_files)} source files."),
        )
    if file_name not in processed.source_files:
        available = ", ".join(processed.source_files.keys())
        raise ValueError(
            f"File '{file_name}' not found in the source code for this contract. Available files: {available}"
        )
    return build_tool_response(
        data=ContractSourceFile(file_content=processed.source_files[file_name]),
        content_text=f'Source file "{file_name}" for contract {address} on chain {chain_id}.',
    )
