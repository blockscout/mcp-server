"""Tests for XML formatting functions."""

from blockscout_mcp_server.formatting.xml_formatters import (
    format_block_time_estimation_rules_xml,
    format_chain_id_guidance_xml,
    format_efficiency_optimization_rules_xml,
    format_error_handling_rules_xml,
    format_mcp_server_version_xml,
    format_pagination_rules_xml,
    format_time_based_query_rules_xml,
)


def test_format_mcp_server_version_xml():
    version_xml = format_mcp_server_version_xml()
    assert version_xml.startswith("<mcp_server_version>")
    assert version_xml.endswith("</mcp_server_version>")


def test_format_error_handling_rules_xml():
    xml = format_error_handling_rules_xml()
    assert xml.startswith("<error_handling_rules>")
    assert xml.endswith("</error_handling_rules>")


def test_format_chain_id_guidance_xml():
    xml = format_chain_id_guidance_xml()
    assert "<chain_id_guidance>" in xml
    assert "<rules>" in xml
    assert "<recommended_chains>" in xml


def test_format_pagination_rules_xml():
    xml = format_pagination_rules_xml()
    assert xml.startswith("<pagination_rules>")
    assert xml.endswith("</pagination_rules>")


def test_format_time_based_query_rules_xml():
    xml = format_time_based_query_rules_xml()
    assert xml.startswith("<time_based_query_rules>")
    assert xml.endswith("</time_based_query_rules>")


def test_format_block_time_estimation_rules_xml():
    xml = format_block_time_estimation_rules_xml()
    assert xml.startswith("<block_time_estimation_rules>")
    assert xml.endswith("</block_time_estimation_rules>")


def test_format_efficiency_optimization_rules_xml():
    xml = format_efficiency_optimization_rules_xml()
    assert xml.startswith("<efficiency_optimization_rules>")
    assert xml.endswith("</efficiency_optimization_rules>")
