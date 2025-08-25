<get_chains_list>
Get the list of known blockchain chains with their IDs.
Useful for getting a chain ID when the chain name is known.
This information can be used in other tools that require a chain ID to request information.
</get_chains_list>

<get_block_info>
Get block information like timestamp, gas used, burnt fees, transaction count etc.
Can optionally include the list of transaction hashes contained in the block. Transaction hashes are omitted by default; request them only when you truly need them, because on high-traffic chains the list may exhaust the context.
</get_block_info>

<get_latest_block>
Get the latest indexed block number and timestamp, which represents the most recent state of the blockchain.
No transactions or token transfers can exist beyond this point, making it useful as a reference timestamp for other API calls.
</get_latest_block>

<get_address_by_ens_name>
Useful for when you need to convert an ENS domain name (e.g. "blockscout.eth") to its corresponding Ethereum address.
</get_address_by_ens_name>

<get_transactions_by_address>
Retrieves native currency transfers and smart contract interactions (calls, internal txs) for an address.
**EXCLUDES TOKEN TRANSFERS**: Filters out direct token balance changes (ERC-20, etc.). You'll see calls *to* token contracts, but not the `Transfer` events. For token history, use `get_token_transfers_by_address`.
A single tx can have multiple records from internal calls; use `internal_transaction_index` for execution order.
Use cases:
    - `get_transactions_by_address(address, age_from)` - get all txs to/from the address since a given date.
    - `get_transactions_by_address(address, age_from, age_to)` - get all txs to/from the address between given dates.
    - `get_transactions_by_address(address, age_from, age_to, methods)` - get all txs to/from the address between given dates, filtered by method.
**SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
</get_transactions_by_address>

<get_token_transfers_by_address>
Get ERC-20 token transfers for an address within a specific time range.
Use cases:
    - `get_token_transfers_by_address(address, age_from)` - get all transfers of any ERC-20 token to/from the address since the given date up to the current time
    - `get_token_transfers_by_address(address, age_from, age_to)` - get all transfers of any ERC-20 token to/from the address between the given dates
    - `get_token_transfers_by_address(address, age_from, age_to, token)` - get all transfers of the given ERC-20 token to/from the address between the given dates
**SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
</get_token_transfers_by_address>

<lookup_token_by_symbol>
Search for token addresses by symbol or name. Returns multiple potential matches based on symbol or token name similarity. Only the first 7 matches from the Blockscout API are returned.
</lookup_token_by_symbol>

<get_contract_abi>
Get smart contract ABI (Application Binary Interface).
An ABI defines all functions, events, their parameters, and return types. The ABI is required to format function calls or interpret contract data.
</get_contract_abi>

<inspect_contract_code>
Inspects a verified contract's source code or metadata.
</inspect_contract_code>

<read_contract>
Calls a smart contract function (view/pure, or non-view/pure simulated via eth_call) and returns the decoded result.

This tool provides a direct way to query the state of a smart contract.

Example:
To check the USDT balance of an address on Ethereum Mainnet, you would use the following arguments:

```json
{
    "tool_name": "read_contract",
    "params": {
    "chain_id": "1",
    "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "abi": {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": false,
        "stateMutability": "view",
        "type": "function"
    },
    "function_name": "balanceOf",
    "args": ["0xF977814e90dA44bFA03b6295A0616a897441aceC"]
    }
}
```
</read_contract>

<get_address_info>
Get comprehensive information about an address, including:

- Address existence check
- Native token (ETH) balance (provided as is, without adjusting by decimals)
- ENS name association (if any)
- Contract status (whether the address is a contract, whether it is verified)
- Proxy contract information (if applicable): determines if a smart contract is a proxy contract (which forwards calls to implementation contracts), including proxy type and implementation addresses
- Token details (if the contract is a token): name, symbol, decimals, total supply, etc.
Essential for address analysis, contract investigation, token research, and DeFi protocol analysis.
</get_address_info>

<get_tokens_by_address>
Get comprehensive ERC20 token holdings for an address with enriched metadata and market data.
Returns detailed token information including contract details (name, symbol, decimals), market metrics (exchange rate, market cap, volume), holders count, and actual balance (provided as is, without adjusting by decimals).
Essential for portfolio analysis, wallet auditing, and DeFi position tracking.
**SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
</get_tokens_by_address>

<transaction_summary>
Get human-readable transaction summaries from Blockscout Transaction Interpreter.
Automatically classifies transactions into natural language descriptions (transfers, swaps, NFT sales, DeFi operations)
Essential for rapid transaction comprehension, dashboard displays, and initial analysis.
Note: Not all transactions can be summarized and accuracy is not guaranteed for complex patterns.
</transaction_summary>

<nft_tokens_by_address>
Retrieve NFT tokens (ERC-721, ERC-404, ERC-1155) owned by an address, grouped by collection.
Provides collection details (type, address, name, symbol, total supply, holder count) and individual token instance data (ID, name, description, external URL, metadata attributes).
Essential for a detailed overview of an address's digital collectibles and their associated collection data.
**SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
</nft_tokens_by_address>

<get_transaction_info>
Get comprehensive transaction information.
Unlike standard eth_getTransactionByHash, this tool returns enriched data including decoded input parameters, detailed token transfers with token metadata, transaction fee breakdown (priority fees, burnt fees) and categorized transaction types.
By default, the raw transaction input is omitted if a decoded version is available to save context; request it with `include_raw_input=True` only when you truly need the raw hex data.
Essential for transaction analysis, debugging smart contract interactions, tracking DeFi operations.
</get_transaction_info>

<get_transaction_logs>
Get comprehensive transaction logs.
Unlike standard eth_getLogs, this tool returns enriched logs, primarily focusing on decoded event parameters with their types and values (if event decoding is applicable).
Essential for analyzing smart contract events, tracking token transfers, monitoring DeFi protocol interactions, debugging event emissions, and understanding complex multi-contract transaction flows.
**SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
</get_transaction_logs>
