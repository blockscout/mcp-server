"""Combined instruction formatting functions."""

from blockscout_mcp_server.formatting.xml_formatters import (
    format_block_time_estimation_rules_xml,
    format_chain_id_guidance_xml,
    format_efficiency_optimization_rules_xml,
    format_error_handling_rules_xml,
    format_mcp_server_version_xml,
    format_pagination_rules_xml,
    format_time_based_query_rules_xml,
)


def format_all_instructions_as_xml_strings() -> list[str]:
    """Format all server instructions as a list of XML-tagged strings."""
    return [
        format_mcp_server_version_xml(),
        format_error_handling_rules_xml(),
        format_chain_id_guidance_xml(),
        format_pagination_rules_xml(),
        format_time_based_query_rules_xml(),
        format_block_time_estimation_rules_xml(),
        format_efficiency_optimization_rules_xml(),
    ]
