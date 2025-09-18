from typing import Any

from mcp.server.fastmcp import Context

from blockscout_mcp_server.cache import CachedContract, contract_cache
from blockscout_mcp_server.tools.common import (
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)


def _determine_file_path(raw_data: dict[str, Any]) -> str:
    """Determine the appropriate file path for a contract source file based on language."""
    file_path = raw_data.get("file_path")
    if not file_path or file_path == ".sol":
        language = raw_data.get("language", "").lower()
        if language == "solidity":
            file_path = f"{raw_data.get('name', 'Contract')}.sol"
        else:
            file_path = f"{raw_data.get('name', 'Contract')}.vy"
    return file_path


async def _fetch_and_process_contract(chain_id: str, address: str, ctx: Context) -> CachedContract:
    """Fetch contract data from cache or Blockscout API."""

    normalized_address = address.lower()
    cache_key = f"{chain_id}:{normalized_address}"
    if cached := await contract_cache.get(cache_key):
        return cached

    base_url = await get_blockscout_base_url(chain_id)
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Resolved Blockscout instance URL.",
    )
    api_path = f"/api/v2/smart-contracts/{normalized_address}"
    raw_data = await make_blockscout_request(base_url=base_url, api_path=api_path)
    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Successfully fetched contract data.",
    )
    raw_data.setdefault("name", normalized_address)
    for key in [
        "language",
        "compiler_version",
        "verified_at",
        "optimization_enabled",
        "optimization_runs",
        "evm_version",
        "license_type",
        "proxy_type",
        "is_fully_verified",
        "decoded_constructor_args",
    ]:
        raw_data.setdefault(key, None)

    source_files: dict[str, str] = {}
    if raw_data.get("source_code"):
        if raw_data.get("additional_sources"):
            main_file_path = _determine_file_path(raw_data)
            source_files[main_file_path] = raw_data.get("source_code")
            for item in raw_data.get("additional_sources", []):
                item_path = item.get("file_path")
                if item_path:
                    source_files[item_path] = item.get("source_code")
        else:
            file_path = _determine_file_path(raw_data)
            source_files[file_path] = raw_data.get("source_code")

    # Create a copy to avoid mutating the original raw_data
    metadata_copy = raw_data.copy()

    # Process constructor args on the copy instead of the original
    from blockscout_mcp_server.tools.common import _truncate_constructor_args  # Local import to avoid cycles

    processed_args, truncated_flag = _truncate_constructor_args(metadata_copy.get("constructor_args"))
    metadata_copy["constructor_args"] = processed_args
    metadata_copy["constructor_args_truncated"] = truncated_flag
    if metadata_copy["decoded_constructor_args"]:
        processed_decoded, decoded_truncated = _truncate_constructor_args(metadata_copy["decoded_constructor_args"])
        metadata_copy["decoded_constructor_args"] = processed_decoded
        if decoded_truncated:
            metadata_copy["constructor_args_truncated"] = True
    metadata_copy["source_code_tree_structure"] = list(source_files.keys())
    for field in [
        "abi",
        "deployed_bytecode",
        "creation_bytecode",
        "source_code",
        "additional_sources",
        "file_path",
    ]:
        metadata_copy.pop(field, None)

    cached_contract = CachedContract(metadata=metadata_copy, source_files=source_files)
    await contract_cache.set(cache_key, cached_contract)
    return cached_contract
