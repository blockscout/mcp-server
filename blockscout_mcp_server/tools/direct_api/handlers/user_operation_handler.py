"""Specialized handler for processing user operation responses."""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import ToolResponse, UserOperationData
from blockscout_mcp_server.tools.common import _recursively_truncate_and_flag_long_strings, build_tool_response
from blockscout_mcp_server.tools.direct_api.dispatcher import register_handler

PATTERN = r"^/api/v2/proxy/account-abstraction/operations/(?P<user_operation_hash>0x[a-fA-F0-9]{64})/?$"


def _truncate_string_field(data: dict[str, Any], field: str, flag_field: str) -> bool:
    value = data.get(field)
    if isinstance(value, str) and len(value) > INPUT_DATA_TRUNCATION_LIMIT:
        data[field] = value[:INPUT_DATA_TRUNCATION_LIMIT]
        data[flag_field] = True
        return True
    return False


def _truncate_decoded_parameters(data: dict[str, Any], field: str) -> bool:
    decoded_value = data.get(field)
    if isinstance(decoded_value, dict) and "parameters" in decoded_value:
        processed_parameters, was_truncated = _recursively_truncate_and_flag_long_strings(
            decoded_value.get("parameters")
        )
        decoded_copy = decoded_value.copy()
        decoded_copy["parameters"] = processed_parameters
        data[field] = decoded_copy
        return was_truncated
    return False


def _optimize_address_field(data: dict[str, Any], field: str) -> None:
    value = data.get(field)
    if isinstance(value, dict):
        data[field] = value.get("hash")


@register_handler(PATTERN)
async def handle_user_operation(
    *,
    match: re.Match[str],
    response_json: dict[str, Any],
    chain_id: str,
    base_url: str,
    ctx: Context,  # noqa: ARG001 - reserved for future use in handlers
    query_params: dict[str, Any] | None = None,  # noqa: ARG001 - not used by this endpoint but required by dispatcher
) -> ToolResponse[UserOperationData]:
    """Process the raw JSON response for a user operation request."""
    user_operation_hash = match.group("user_operation_hash")

    if not isinstance(response_json, dict):
        raise RuntimeError("Blockscout API returned an unexpected format for user operation")

    transformed_data = response_json.copy()
    was_truncated = False

    raw_data = transformed_data.get("raw")
    if isinstance(raw_data, dict):
        raw_copy = raw_data.copy()
        raw_was_truncated = False
        raw_was_truncated |= _truncate_string_field(raw_copy, "call_data", "raw_call_data_truncated")
        raw_was_truncated |= _truncate_string_field(raw_copy, "paymaster_and_data", "raw_paymaster_and_data_truncated")
        raw_was_truncated |= _truncate_string_field(raw_copy, "signature", "raw_signature_truncated")
        transformed_data["raw"] = raw_copy
        if raw_was_truncated:
            for flag_key in ("raw_call_data_truncated", "raw_paymaster_and_data_truncated", "raw_signature_truncated"):
                if raw_copy.get(flag_key):
                    transformed_data[flag_key] = True
            was_truncated = True

    decoded_call_truncated = _truncate_decoded_parameters(transformed_data, "decoded_call_data")
    decoded_execute_truncated = _truncate_decoded_parameters(transformed_data, "decoded_execute_call_data")
    was_truncated = was_truncated or decoded_call_truncated or decoded_execute_truncated

    was_truncated |= _truncate_string_field(transformed_data, "call_data", "call_data_truncated")
    was_truncated |= _truncate_string_field(transformed_data, "execute_call_data", "execute_call_data_truncated")
    was_truncated |= _truncate_string_field(transformed_data, "signature", "signature_truncated")
    was_truncated |= _truncate_string_field(transformed_data, "aggregator_signature", "aggregator_signature_truncated")

    for address_field in ("sender", "factory", "paymaster", "entry_point", "bundler", "execute_target"):
        _optimize_address_field(transformed_data, address_field)

    data = UserOperationData(**transformed_data)

    data_description = [
        "User Operation Fields:",
        "- `hash`: User operation hash (identifier for ERC-4337 operation)",
        "- `sender`: Account that initiated the user operation (address string)",
        "- `entry_point`: ERC-4337 entry point address (string)",
        "- `paymaster`: Optional paymaster address (string or null)",
        "- `factory`: Optional factory address (string or null)",
        "- `bundler`: Bundler address (string or null)",
        "- `execute_target`: Execute target address (string or null)",
        "Decoded Call Data:",
        "- `decoded_call_data`: Decoded call data for the user operation",
        "- `decoded_execute_call_data`: Decoded call data for execution wrapper (if available)",
        "- `parameters`: Decoded parameters; long values may be truncated and flagged.",
    ]

    notes = None
    if was_truncated:
        notes = [
            (
                "One or more fields in this user operation response were too large and have been truncated. "
                "Look for `*_truncated` or `raw_*_truncated` flags to identify shortened fields."
            ),
            "To retrieve the full, untruncated data, request the user operation directly. For example:",
            f'`curl "{base_url}/api/v2/proxy/account-abstraction/operations/{user_operation_hash}"`',
        ]

    return build_tool_response(
        data=data,
        data_description=data_description,
        notes=notes,
    )
