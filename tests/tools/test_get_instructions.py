# tests/tools/test_get_instructions.py
import pytest
from unittest.mock import patch

from blockscout_mcp_server.tools.get_instructions import __get_instructions__

@pytest.mark.asyncio
async def test_get_instructions_success(mock_ctx):
    """
    Verify __get_instructions__ returns the SERVER_INSTRUCTIONS constant.
    """
    # ARRANGE
    # Mock the SERVER_INSTRUCTIONS constant
    expected_instructions = """You are an AI assistant with access to Blockscout blockchain data. Use the available tools to:

1. Look up blockchain information (addresses, blocks, transactions, contracts)
2. Resolve ENS domain names to addresses
3. Search for tokens by symbol
4. Get contract ABIs and smart contract information
5. Find NFT and token holdings for addresses

Always provide chain_id as the first parameter for blockchain-specific queries.
Use descriptive responses and explain what the data means in context."""

    with patch('blockscout_mcp_server.tools.get_instructions.SERVER_INSTRUCTIONS', expected_instructions):
        # ACT
        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert result == expected_instructions
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_instructions_no_progress_tracking(mock_ctx):
    """
    Verify __get_instructions__ works correctly even without progress tracking.
    """
    # ARRANGE
    expected_instructions = "Test instructions content"

    with patch('blockscout_mcp_server.tools.get_instructions.SERVER_INSTRUCTIONS', expected_instructions):
        # ACT
        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert result == expected_instructions
        # Verify progress was reported
        assert mock_ctx.report_progress.call_count == 2
        
        # Verify the specific progress calls
        progress_calls = mock_ctx.report_progress.call_args_list
        
        # First call should be starting
        start_call = progress_calls[0]
        assert start_call[1]['progress'] == 0.0
        assert start_call[1]['total'] == 1.0
        assert "Fetching server instructions" in start_call[1]['message']
        
        # Second call should be completion
        end_call = progress_calls[1]
        assert end_call[1]['progress'] == 1.0
        assert end_call[1]['total'] == 1.0
        assert "Server instructions ready" in end_call[1]['message']

@pytest.mark.asyncio
async def test_get_instructions_empty_instructions(mock_ctx):
    """
    Verify __get_instructions__ handles empty SERVER_INSTRUCTIONS gracefully.
    """
    # ARRANGE
    expected_instructions = ""

    with patch('blockscout_mcp_server.tools.get_instructions.SERVER_INSTRUCTIONS', expected_instructions):
        # ACT
        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert result == expected_instructions
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_instructions_multiline_instructions(mock_ctx):
    """
    Verify __get_instructions__ correctly handles multiline instructions.
    """
    # ARRANGE
    expected_instructions = """Line 1 of instructions
Line 2 of instructions
Line 3 of instructions

With empty lines and formatting."""

    with patch('blockscout_mcp_server.tools.get_instructions.SERVER_INSTRUCTIONS', expected_instructions):
        # ACT
        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert result == expected_instructions
        assert "Line 1 of instructions" in result
        assert "Line 2 of instructions" in result
        assert "Line 3 of instructions" in result
        assert "With empty lines and formatting." in result
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_instructions_special_characters(mock_ctx):
    """
    Verify __get_instructions__ handles instructions with special characters.
    """
    # ARRANGE
    expected_instructions = """Instructions with special chars: !@#$%^&*()
Unicode: 📝 🔍 ⚡
Quotes: "double" and 'single'
Escapes: \n \t \\"""

    with patch('blockscout_mcp_server.tools.get_instructions.SERVER_INSTRUCTIONS', expected_instructions):
        # ACT
        result = await __get_instructions__(ctx=mock_ctx)

        # ASSERT
        assert result == expected_instructions
        assert "!@#$%^&*()" in result
        assert "📝 🔍 ⚡" in result
        assert '"double"' in result
        assert "'single'" in result
        assert mock_ctx.report_progress.call_count == 2 