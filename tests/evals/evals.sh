# get_block_info
# get_latest_block
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'What is the block number of the Ethereum Mainnet that corresponds to midnight (or any closer moment) of the 1st of July. Final answer is a block number.'

# get_address_info
# get_address_by_ens_name
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'What address balance of `ens.eth`? Final answer is a decimal (e.g. 123.456)'

# docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'Which 10 most recent logs were emitted by 0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7 before "Nov 08 2024 04:21:35 AM (-06:00 UTC)"?'

# get_transactions_by_address
# get_transaction_info
# get_contract_abi
# lookup_token_by_symbol
# get_address_by_ens_name
# get_chains_list
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'Is any approval set for OP token on Optimism chain by `zeaver.eth`? Final answer is the list where the first element is transaction where approval was set, the second element is the approval amount and the third element is the spender address.'

# docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'Tell me more about the transaction `0xf8a55721f7e2dcf85690aaf81519f7bc820bc58a878fa5f81b12aef5ccda0efb` on Redstone rollup.'

# get_transactions_by_address
# get_block_info
# get_latest_block
# get_chains_list
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-flash -p 'What is the latest block on Gnosis Chain and who is the block minter? Were any funds moved from this minter recently? Final answer is a the list where the first element is minter, the second element is transaction hash and the third element is a recipient address.'

# get_token_transfers_by_address
# get_latest_block
# lookup_token_by_symbol
# get_chains_list
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'When the most recent reward distribution of Kinto token was made to the wallet `0x7D467D99028199D99B1c91850C4dea0c82aDDF52` in Kinto chain? Final answer is a transaction hash.'

# get_contract_abi
# inspect_contract_code
# read_contract
# lookup_token_by_symbol
# get_chains_list
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-flash -p 'Is there any blacklisting functionality of USDT token on Arbitrum One? Final answer is "yes" or "no"'

# read_contract
# get_contract_abi
# lookup_token_by_symbol
# get_latest_block
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-flash -p 'Get the usdt token balance for `0xF977814e90dA44bFA03b6295A0616a897441aceC` on the ethereum mainnet at the block previous to the current block. Final answer is a decimal (e.g. 123.456)'

# inspect_contract_code
# get_contract_abi
# get_address_info
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'Which methods of `0x1c479675ad559DC151F6Ec7ed3FbF8ceE79582B6` on the Ethereum mainnet could emit `SequencerBatchDelivered`? Final answer is a comma separated list of method names (e.g. ["addLiquidity", "removeLiquidity"]).'

# direct_api_call
# get_chains_list
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'What is the most recent completed cross chain message sent from the Arbitrum Sepolia rollup to the base layer? Final answer is a transaction in the rollup.'

# get_tokens_by_address
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'How many different stablecoins does `0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1` (Optimism Gateway) on Ethereum Mainnet hold with balance more than $1,000,000? Final answer is the list of token symbols (e.g. ["USDT", "FRAX"])'

# transaction_summary
# get_transaction_logs
# get_transaction_info
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-flash -p 'Make comprehensive analysis of the transaction `0x6a6c375ea5c9370727cad7c69326a5f55db7b049623fba0e7ac52704b2778ba8` on Ethereum Mainnet. And answer what could be one word category for it. Collect as much details for this operation as you can before the answer. Final answer is one word.'

# nft_tokens_by_address
# get_address_by_ens_name
docker compose run --rm -i evaluation gemini -y -m gemini-2.5-pro -p 'How many tokens of NFT collection "ApePunks" owned by `🇵🇱pl.eth` on Ethereum Mainnet? Final answer is with a number.'