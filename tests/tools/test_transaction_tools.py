# tests/tools/test_transaction_tools.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.transaction_tools import (
    get_transactions_by_address, 
    get_token_transfers_by_address,
    transaction_summary
)

@pytest.mark.asyncio
async def test_get_transactions_by_address_calls_wrapper_correctly(mock_ctx):
    """
    Verify get_transactions_by_address calls the periodic progress wrapper with correct arguments.
    This tests the integration without testing the wrapper's internal logic.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    age_from = "2023-01-01T00:00:00.00Z"
    age_to = "2023-01-02T00:00:00.00Z"
    methods = "0x304e6ade"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {"items": [], "next_page_params": None}

    # We patch the wrapper and the base URL getter
    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress', new_callable=AsyncMock) as mock_wrapper:

        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id, 
            address=address, 
            age_from=age_from,
            age_to=age_to,
            methods=methods,
            ctx=mock_ctx
        )

        # ASSERT
        assert result == mock_api_response
        mock_get_url.assert_called_once_with(chain_id)

        # Assert that the wrapper was called once
        mock_wrapper.assert_called_once()

        # Assert that the wrapper was called with the correct arguments
        # This is the most important part of this test.
        call_args, call_kwargs = mock_wrapper.call_args
        
        # Verify the wrapper was called with correct parameters
        assert call_kwargs['ctx'] == mock_ctx
        
        # Import the actual function to compare
        from blockscout_mcp_server.tools.common import make_blockscout_request
        assert call_kwargs['request_function'] == make_blockscout_request
        
        # Check the request_args that should be passed to make_blockscout_request
        expected_request_args = {
            "base_url": mock_base_url,
            "api_path": "/api/v2/advanced-filters",
            "params": {
                "to_address_hashes_to_include": address,
                "from_address_hashes_to_include": address,
                "age_from": age_from,
                "age_to": age_to,
                "methods": methods
            }
        }
        assert call_kwargs['request_args'] == expected_request_args
        
        # Verify other wrapper configuration
        assert call_kwargs['tool_overall_total_steps'] == 2.0
        assert call_kwargs['current_step_number'] == 2.0
        assert call_kwargs['current_step_message_prefix'] == "Fetching transactions"
        assert "total_duration_hint" in call_kwargs
        assert "progress_interval_seconds" in call_kwargs
        
        # Verify progress was reported correctly before the wrapper call
        assert mock_ctx.report_progress.call_count == 2  # Start + after URL resolution

@pytest.mark.asyncio
async def test_get_transactions_by_address_minimal_params(mock_ctx):
    """
    Verify get_transactions_by_address works with minimal parameters (only required ones).
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {"items": [{"hash": "0xabc123"}]}

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress', new_callable=AsyncMock) as mock_wrapper:

        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response

        # ACT - Only provide required parameters
        result = await get_transactions_by_address(
            chain_id=chain_id, 
            address=address, 
            ctx=mock_ctx
        )

        # ASSERT
        assert result == mock_api_response
        mock_get_url.assert_called_once_with(chain_id)
        mock_wrapper.assert_called_once()

        # Check that the request_args only include the required parameters
        call_args, call_kwargs = mock_wrapper.call_args
        expected_params = {
            "to_address_hashes_to_include": address,
            "from_address_hashes_to_include": address
            # No optional parameters should be included
        }
        assert call_kwargs['request_args']['params'] == expected_params

@pytest.mark.asyncio
async def test_get_token_transfers_by_address_calls_wrapper_correctly(mock_ctx):
    """
    Verify get_token_transfers_by_address calls the periodic progress wrapper with correct arguments.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    age_from = "2023-01-01T00:00:00.00Z"
    age_to = "2023-01-02T00:00:00.00Z"
    token = "0xA0b86a33E6441d95d7a9b6F25b0f2F5D6C16eD97"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {"items": [], "next_page_params": None}

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress', new_callable=AsyncMock) as mock_wrapper:

        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response

        # ACT
        result = await get_token_transfers_by_address(
            chain_id=chain_id, 
            address=address, 
            age_from=age_from,
            age_to=age_to,
            token=token,
            ctx=mock_ctx
        )

        # ASSERT
        assert result == mock_api_response
        mock_get_url.assert_called_once_with(chain_id)
        mock_wrapper.assert_called_once()

        # Check the wrapper call arguments
        call_args, call_kwargs = mock_wrapper.call_args
        assert call_kwargs['ctx'] == mock_ctx
        
        from blockscout_mcp_server.tools.common import make_blockscout_request
        assert call_kwargs['request_function'] == make_blockscout_request
        
        # Check the request_args for token transfers
        expected_request_args = {
            "base_url": mock_base_url,
            "api_path": "/api/v2/advanced-filters",
            "params": {
                "transaction_types": "ERC-20",
                "to_address_hashes_to_include": address,
                "from_address_hashes_to_include": address,
                "age_from": age_from,
                "age_to": age_to,
                "token_contract_address_hashes_to_include": token
            }
        }
        assert call_kwargs['request_args'] == expected_request_args
        
        # Verify other wrapper configuration
        assert call_kwargs['tool_overall_total_steps'] == 2.0
        assert call_kwargs['current_step_number'] == 2.0
        assert call_kwargs['current_step_message_prefix'] == "Fetching token transfers"
        
        # Verify progress was reported correctly before the wrapper call
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_token_transfers_by_address_chain_error(mock_ctx):
    """
    Verify that chain lookup errors are properly propagated without calling the wrapper.
    """
    # ARRANGE
    chain_id = "999999"  # Invalid chain ID
    address = "0x123abc"

    from blockscout_mcp_server.tools.common import ChainNotFoundError
    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress', new_callable=AsyncMock) as mock_wrapper:

        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_token_transfers_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # Verify the chain lookup was attempted
        mock_get_url.assert_called_once_with(chain_id)
        
        # Verify the wrapper was NOT called since chain lookup failed
        mock_wrapper.assert_not_called()
        
        # Progress should have been reported once (at start) before the error
        assert mock_ctx.report_progress.call_count == 1
        assert mock_ctx.info.call_count == 1

@pytest.mark.asyncio
async def test_get_transactions_by_address_wrapper_error(mock_ctx):
    """
    Verify that errors from the periodic progress wrapper are properly propagated.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Simulate an error from the wrapper (which could be an API error or timeout)
    wrapper_error = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503))

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress', new_callable=AsyncMock) as mock_wrapper:

        mock_get_url.return_value = mock_base_url
        mock_wrapper.side_effect = wrapper_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # Verify the chain lookup succeeded
        mock_get_url.assert_called_once_with(chain_id)
        
        # Verify the wrapper was called and failed
        mock_wrapper.assert_called_once()
        
        # Progress should have been reported twice (start + after URL resolution) before the wrapper error
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2

@pytest.mark.asyncio
async def test_transaction_summary_without_wrapper(mock_ctx):
    """
    Test a transaction tool that doesn't use the periodic progress wrapper for comparison.
    This helps verify our testing approach for wrapper vs non-wrapper tools.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    
    mock_api_response = {
        "data": {
            "summaries": "This is a test transaction summary."
        }
    }
    expected_result = "# Transaction Summary from Blockscout Transaction Interpreter\nThis is a test transaction summary."

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await transaction_summary(chain_id=chain_id, hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert result == expected_result
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, 
            api_path=f"/api/v2/transactions/{tx_hash}/summary"
        )
        
        # This tool should have 3 progress reports (start, after URL, completion)
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_transaction_summary_no_summary_available(mock_ctx):
    """
    Test transaction_summary when no summary is available in the response.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    
    # Response with no summary data
    mock_api_response = {
        "data": {}
    }
    expected_result = "No summary available."

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await transaction_summary(chain_id=chain_id, hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert result == expected_result
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{tx_hash}/summary"
        )
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3
