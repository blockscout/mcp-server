ADVANCED API USAGE: For specialized or chain-specific data not covered by other tools, you can use `direct_api_call`. This tool can call a curated list of raw Blockscout API endpoints.

<common>
<group name="Stats">
"/stats-service/api/v1/counters" - "Get consolidated historical and recent-window counters—totals and 24h/30m rollups for blockchain activity (transactions, accounts, contracts, verified contracts, ERC-4337 user ops), plus average block time and fee aggregates"
"/api/v2/stats" - "Get real-time network status and market context—current gas price tiers with last-update and next-update timing, network utilization, today's transactions, average block time 'now', and coin price/market cap."
</group>
<group name="User Operations">
"/api/v2/proxy/account-abstraction/operations/{user_operation_hash}" - "Get details for a specific User Operation by its hash."
</group>
<group name="Tokens & NFTs">
"/api/v2/tokens/{token_contract_address}/instances" - "Get all NFT instances for a given token contract address."
"/api/v2/tokens/{token_contract_address}/holders" - "Get a list of holders for a given token."
"/api/v2/tokens/{token_contract_address}/instances/{instance_id}" - "Get details for a specific NFT instance."
"/api/v2/tokens/{token_contract_address}/instances/{instance_id}/transfers" - "Get transfer history for a specific NFT instance."
</group>
</common>

<specific>
<chain_family name="Ethereum Mainnet and Gnosis">
"/api/v2/addresses/{account_address}/beacon/deposits" - "Get Beacon Chain deposits for a specific address."
"/api/v2/blocks/{block_number}/beacon/deposits" - "Get Beacon Chain deposits for a specific block."
"/api/v2/addresses/{account_address}/withdrawals" - "Get Beacon Chain withdrawals for a specific address."
"/api/v2/blocks/{block_number}/withdrawals" - "Get Beacon Chain withdrawals for a specific block."
</chain_family>
<chain_family name="Arbitrum">
"/api/v2/main-page/arbitrum/batches/latest-number" - "Get the latest committed batch number for Arbitrum."
"/api/v2/arbitrum/batches/{batch_number}" - "Get information for a specific Arbitrum batch."
"/api/v2/arbitrum/messages/to-rollup" - "Get L1 to L2 messages for Arbitrum."
"/api/v2/arbitrum/messages/from-rollup" - "Get L2 to L1 messages for Arbitrum."
"/api/v2/arbitrum/messages/withdrawals/{transaction_hash}" - "Get L2 to L1 messages for a specific transaction hash on Arbitrum."
</chain_family>
<chain_family name="Optimism">
"/api/v2/optimism/batches" - "Get the latest committed batches for Optimism."
"/api/v2/optimism/batches/{batch_number}" - "Get information for a specific Optimism batch."
"/api/v2/optimism/games" - "Get dispute games for Optimism."
"/api/v2/optimism/deposits" - "Get L1 to L2 messages (deposits) for Optimism."
"/api/v2/optimism/withdrawals" - "Get L2 to L1 messages (withdrawals) for Optimism."
</chain_family>
<chain_family name="Celo">
"/api/v2/celo/epochs" - "Get the latest finalized epochs for Celo."
"/api/v2/celo/epochs/{epoch_number}" - "Get information for a specific Celo epoch."
"/api/v2/celo/epochs/{epoch_number}/election-rewards/group" - "Get validator group rewards for a specific Celo epoch."
"/api/v2/celo/epochs/{epoch_number}/election-rewards/validator" - "Get validator rewards for a specific Celo epoch."
"/api/v2/celo/epochs/{epoch_number}/election-rewards/voter" - "Get voter rewards for a specific Celo epoch."
</chain_family>
<chain_family name="zkSync">
"/api/v2/main-page/zksync/batches/latest-number" - "Get the latest committed batch number for zkSync."
"/api/v2/zksync/batches/{batch_number}" - "Get information for a specific zkSync batch."
</chain_family>
<chain_family name="zkEVM">
"/api/v2/zkevm/batches/confirmed" - "Get the latest confirmed batches for zkEVM."
"/api/v2/zkevm/batches/{batch_number}" - "Get information for a specific zkEVM batch."
"/api/v2/zkevm/deposits" - "Get deposits for zkEVM."
"/api/v2/zkevm/withdrawals" - "Get withdrawals for zkEVM."
</chain_family>
<chain_family name="Scroll">
"/api/v2/scroll/batches" - "Get the latest committed batches for Scroll."
"/api/v2/scroll/batches/{batch_number}" - "Get information for a specific Scroll batch."
"/api/v2/blocks/scroll-batch/{batch_number}" - "Get blocks for a specific Scroll batch."
"/api/v2/scroll/deposits" - "Get L1 to L2 messages (deposits) for Scroll."
"/api/v2/scroll/withdrawals" - "Get L2 to L1 messages (withdrawals) for Scroll."
</chain_family>
<chain_family name="Shibarium">
"/api/v2/shibarium/deposits" - "Get L1 to L2 messages (deposits) for Shibarium."
"/api/v2/shibarium/withdrawals" - "Get L2 to L1 messages (withdrawals) for Shibarium."
</chain_family>
<chain_family name="Stability">
"/api/v2/validators/stability" - "Get the list of validators for Stability."
</chain_family>
<chain_family name="Zilliqa">
"/api/v2/validators/zilliqa" - "Get the list of validators for Zilliqa."
"/api/v2/validators/zilliqa/{validator_public_key}" - "Get information for a specific Zilliqa validator."
</chain_family>
<chain_family name="Redstone">
"/api/v2/mud/worlds" - "Get a list of MUD worlds for Redstone."
"/api/v2/mud/worlds/{contract_address}/tables" - "Get tables for a specific MUD world on Redstone."
"/api/v2/mud/worlds/{contract_address}/tables/{table_id}/records" - "Get records for a specific MUD world table on Redstone."
"/api/v2/mud/worlds/{contract_address}/tables/{table_id}/records/{record_id}" - "Get a specific record from a MUD world table on Redstone."
</chain_family>
</specific>
