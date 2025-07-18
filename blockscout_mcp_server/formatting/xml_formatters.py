"""Individual XML formatting functions for instruction content."""

from blockscout_mcp_server.constants import (
    BLOCK_TIME_ESTIMATION_RULES,
    CHAIN_ID_RULES,
    EFFICIENCY_OPTIMIZATION_RULES,
    ERROR_HANDLING_RULES,
    PAGINATION_RULES,
    RECOMMENDED_CHAINS,
    SERVER_VERSION,
    TIME_BASED_QUERY_RULES,
)


def format_mcp_server_version_xml() -> str:
    """Format MCP server version as XML string."""
    return f"<mcp_server_version>{SERVER_VERSION}</mcp_server_version>"


def format_error_handling_rules_xml() -> str:
    """Format error handling rules as XML string."""
    return f"<error_handling_rules>\n{ERROR_HANDLING_RULES.strip()}\n</error_handling_rules>"


def format_chain_id_guidance_xml() -> str:
    """Format chain ID guidance as XML string."""
    chains_list_str = "\n".join([f"  * {chain['name']}: {chain['chain_id']}" for chain in RECOMMENDED_CHAINS])
    return (
        "<chain_id_guidance>\n"
        "<rules>\n"
        f"{CHAIN_ID_RULES.strip()}\n"
        "</rules>\n"
        "<recommended_chains>\n"
        "Here is the list of IDs of most popular chains:\n"
        f"{chains_list_str}\n"
        "</recommended_chains>\n"
        "</chain_id_guidance>"
    )


def format_pagination_rules_xml() -> str:
    """Format pagination rules as XML string."""
    return f"<pagination_rules>\n{PAGINATION_RULES.strip()}\n</pagination_rules>"


def format_time_based_query_rules_xml() -> str:
    """Format time-based query rules as XML string."""
    return f"<time_based_query_rules>\n{TIME_BASED_QUERY_RULES.strip()}\n</time_based_query_rules>"


def format_block_time_estimation_rules_xml() -> str:
    """Format block time estimation rules as XML string."""
    return f"<block_time_estimation_rules>\n{BLOCK_TIME_ESTIMATION_RULES.strip()}\n</block_time_estimation_rules>"


def format_efficiency_optimization_rules_xml() -> str:
    """Format efficiency optimization rules as XML string."""
    return f"<efficiency_optimization_rules>\n{EFFICIENCY_OPTIMIZATION_RULES.strip()}\n</efficiency_optimization_rules>"
