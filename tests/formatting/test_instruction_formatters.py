"""Tests for combined instruction formatting functions."""

from blockscout_mcp_server.formatting.instruction_formatters import (
    format_all_instructions_as_xml_strings,
)


def test_format_all_instructions_as_xml_strings():
    result = format_all_instructions_as_xml_strings()
    assert isinstance(result, list)
    assert len(result) == 7
    for item in result:
        assert isinstance(item, str)
        assert item.startswith("<")
        assert item.endswith(">")

    all_text = " ".join(result)
    assert "<chain_id_guidance>" in all_text
    assert "<error_handling_rules>" in all_text
