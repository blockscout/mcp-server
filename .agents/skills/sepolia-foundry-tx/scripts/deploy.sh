#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-Blockscout
#
# Deploy a contract to Sepolia testnet via Foundry, routed through the
# Blockscout PRO API's JSON-RPC gateway. Resolves (a) the signing key from
# the encrypted Foundry keystore under .ai/wallet/ and (b) the RPC endpoint
# + Authorization header for the PRO API gateway, then runs the real
# `forge create`/`forge script` command with those flags appended -- forge's
# own stdout/stderr reach the caller exactly as if forge had been invoked
# directly. This wrapper only automates the credential/endpoint plumbing,
# not the deployment itself.
#
# This script never adds --broadcast on its own -- pass it yourself (as one
# of the forwarded forge args) once you're ready to send a real transaction.
# Without it, forge only simulates the deployment; nothing is broadcast, and
# the script exits with forge's own exit code (nothing below applies).
#
# --gas-limit defaults to 2500000 if you don't pass one (or set $ETH_GAS_LIMIT)
# -- the gateway can't auto-estimate gas for contract creation (see
# references/pro-api-auth.md). Override it for an unusually large contract,
# or if a deployment reverts out of gas. Note the default is sized with
# headroom over typical small-contract usage, not maximally generous --
# the node requires balance >= gas_limit * gas_price just to accept the tx,
# so an overly large default can trip an "InsufficientFunds" preflight on a
# lightly-funded test wallet even though actual billing is only for gas
# used. Before a --broadcast run, this script checks that same
# balance >= gas_limit * gas_price condition itself and exits 7 with the
# deployer's address/balance/requirement if it fails, rather than paying for
# a wasted forge invocation to discover the same thing. --legacy is likewise
# added automatically if you don't pass it, for a related reason (the
# gateway doesn't support forge's default EIP-1559 fee estimation).
#
# *** After --broadcast, forge's own exit code and message are NOT reliable
# on this gateway -- confirmed twice: `forge create` reported
# "Error: contract was not deployed" on runs that had, in fact, succeeded
# on-chain (the gateway's receipt for a contract-creation tx appears to be
# missing something forge's client expects, likely `contractAddress`). So
# this script does NOT exec/trust forge for the final result: after forge
# returns, it independently looks up every transaction the deployer sent
# during this run (by comparing the account's nonce before and after) via
# the Blockscout PRO API's indexed REST endpoint -- not the json-rpc
# gateway, since that's the same surface with the receipt gap -- and reports
# the real on-chain outcome. The script's own exit code reflects that
# verified outcome, not forge's. See references/pro-api-auth.md for how
# this was confirmed -- including a second false-negative found in an
# earlier version of THIS verification step itself (it read a
# not-yet-resolved receipt as a failure); the current retry logic treats an
# unresolved `result`/`status` the same as "not found yet" specifically to
# avoid repeating that mistake.
#
# Usage:
#   deploy.sh <create|script> [--key-name NAME] [--chain-id ID] -- <forge args...>
#
# Examples:
#   deploy.sh create -- src/MyToken.sol:MyToken --constructor-args "Foo" "FOO"
#   deploy.sh create -- src/MyToken.sol:MyToken --constructor-args "Foo" "FOO" --broadcast
#   deploy.sh script -- script/Deploy.s.sol --broadcast
#   deploy.sh create --key-name sepolia-test-deployer -- src/MyToken.sol:MyToken --broadcast
#
# --key-name selects which .ai/wallet/<name> keystore to use when more than
#   one exists; omit it when there is exactly one -- it will be discovered
#   automatically.
# --chain-id overrides the default Sepolia chain id (11155111). Only pass
#   this if the user has explicitly asked to target a different chain --
#   see SKILL.md's safety note before doing so.
#
# Output: forge's own stdout/stderr, unmodified, plus this wrapper's own
#   informational lines on stderr ("Signer:"/"RPC:" always; after
#   --broadcast, "Verifying broadcast result..." followed by one
#   "Verified: nonce N, tx <hash> -- SUCCESS/FAILED [, contract created at
#   <address>]" line per transaction the deployer sent during this run).
# Exit codes (without --broadcast): forge's own exit code, unmodified.
# Exit codes (with --broadcast): reflect the VERIFIED on-chain outcome, not
#   forge's own exit code --
#             0 = every transaction sent during this run succeeded on-chain
#             1 = at least one of them failed/reverted on-chain
#             2 = bad usage
#             3 = signing key could not be resolved (missing/ambiguous)
#             4 = BLOCKSCOUT_PRO_API_KEY not available
#             5 = not inside a git repository
#             6 = a transaction was mined (nonce advanced) but Blockscout
#                 hadn't resolved its final status after retrying for ~60s
#                 -- inconclusive, not a known failure; check manually
#                 before deciding
#             7 = the deployer's balance is below what --broadcast would
#                 require (gas_limit x gas_price) -- caught before forge
#                 even runs; top up the wallet or lower --gas-limit
#   If no new transaction was mined at all (--broadcast was passed but
#   nothing actually got sent), this script falls back to forge's own exit
#   code, since there's nothing on-chain yet to verify.

set -euo pipefail

die() {
  local code="$1"
  shift
  echo "error: $*" >&2
  exit "$code"
}

usage() {
  cat >&2 <<'EOF'
Usage: deploy.sh <create|script> [--key-name NAME] [--chain-id ID] -- <forge args...>
See the script's header comment for examples.
EOF
}

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  die 5 "not inside a git repository"
fi

mode="${1:-}"
case "$mode" in
  create|script) shift ;;
  -h|--help|"") usage; exit 0 ;;
  *) usage; die 2 "unknown mode '$mode' (expected 'create' or 'script')" ;;
esac

key_name=""
chain_id="11155111"
forge_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --key-name) key_name="${2:-}"; shift 2 ;;
    --chain-id) chain_id="${2:-}"; shift 2 ;;
    --) shift; forge_args=("$@"); break ;;
    *) usage; die 2 "unexpected argument '$1' before '--' (wrapper flags must come before the '--' separator)" ;;
  esac
done

if [[ ${#forge_args[@]} -eq 0 ]]; then
  usage
  die 2 "no forge arguments given after '--'"
fi

wallet_dir="$repo_root/.ai/wallet"
if [[ ! -d "$wallet_dir" ]]; then
  die 3 "no $wallet_dir directory -- no signing key has been created yet (see SKILL.md)"
fi

if [[ -n "$key_name" ]]; then
  keystore="$wallet_dir/$key_name"
  passfile="$wallet_dir/$key_name.pass"
  [[ -f "$keystore" && -f "$passfile" ]] || die 3 "no keystore/password pair named '$key_name' under $wallet_dir"
else
  candidates=()
  for f in "$wallet_dir"/*; do
    [[ -f "$f" ]] || continue
    [[ "$f" == *.pass ]] && continue
    [[ -f "$f.pass" ]] && candidates+=("$(basename "$f")")
  done
  case "${#candidates[@]}" in
    0) die 3 "no keystore/password pairs found under $wallet_dir" ;;
    1) key_name="${candidates[0]}" ;;
    *) die 3 "multiple keystore candidates under $wallet_dir: ${candidates[*]} -- pass --key-name <name> to disambiguate" ;;
  esac
  keystore="$wallet_dir/$key_name"
  passfile="$wallet_dir/$key_name.pass"
fi

if [[ -z "${BLOCKSCOUT_PRO_API_KEY:-}" && -f "$repo_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$repo_root/.env"
  set +a
fi
[[ -n "${BLOCKSCOUT_PRO_API_KEY:-}" ]] || die 4 "BLOCKSCOUT_PRO_API_KEY is not set (checked environment and $repo_root/.env)"

# The Blockscout PRO API json-rpc gateway does not support the standard
# to-omitted eth_estimateGas shape used for contract-creation gas estimation
# (it errors "Invalid `to` address"), nor eth_feeHistory (errors "Action not
# found"), which forge's default EIP-1559 fee estimation depends on. Both
# gaps are worked around, not by fixing the gateway: a default --gas-limit
# sidesteps the first (a fixed value can't be right for every contract, but
# a generous one costs nothing extra in actual fees -- gas is billed by
# usage, not by the limit -- so defaulting it removes the need to specify it
# in the common case; override it for an unusually large contract, or if a
# deployment reverts out of gas), and --legacy sidesteps the second (falls
# back to eth_gasPrice, which the gateway does support). See
# references/pro-api-auth.md.
#
# NOTE: the node still requires balance >= gas_limit * gas_price just to
# accept the tx (an "InsufficientFunds" preflight check), even though actual
# billing is only for gas used -- so an overly generous default can fail
# this preflight on a lightly-funded test wallet well before the real cost
# would ever matter. 2,500,000 is sized with headroom over this contract's
# observed real usage (~1,963,456 gas) without reserving much more than
# that against a wallet that may only be topped up in small increments.
DEFAULT_GAS_LIMIT=2500000

has_flag() {
  local flag="$1"
  local a
  for a in "${forge_args[@]}"; do
    [[ "$a" == "$flag" ]] && return 0
  done
  return 1
}

if ! has_flag --gas-limit && [[ -z "${ETH_GAS_LIMIT:-}" ]]; then
  forge_args+=(--gas-limit "$DEFAULT_GAS_LIMIT")
fi

if ! has_flag --legacy; then
  forge_args+=(--legacy)
fi

rpc_url="https://api.blockscout.com/${chain_id}/json-rpc"
rpc_headers="Authorization: Bearer ${BLOCKSCOUT_PRO_API_KEY}"
rest_headers=(--header "$rpc_headers" --header "User-Agent: sepolia-foundry-tx-skill/1.0" --header "Accept: application/json")

broadcasting=false
has_flag --broadcast && broadcasting=true

if $broadcasting && ! command -v jq >/dev/null 2>&1; then
  die 2 "jq is required to verify a --broadcast result against the Blockscout PRO API (see references/pro-api-auth.md) -- install jq"
fi

echo "Signer: $key_name ($keystore)" >&2
echo "RPC:    $rpc_url (chain $chain_id)" >&2

get_nonce() {
  curl -s --request POST --url "$rpc_url" --header "$rpc_headers" --header 'Content-Type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"eth_getTransactionCount\",\"params\":[\"$1\",\"latest\"]}" \
    | jq -r '.result'
}

get_balance() {
  curl -s --request POST --url "$rpc_url" --header "$rpc_headers" --header 'Content-Type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"eth_getBalance\",\"params\":[\"$1\",\"latest\"]}" \
    | jq -r '.result'
}

get_gas_price() {
  curl -s --request POST --url "$rpc_url" --header "$rpc_headers" --header 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_gasPrice","params":[]}' \
    | jq -r '.result'
}

pre_nonce=""
deployer_address=""
if $broadcasting; then
  deployer_address="$(cast wallet address --keystore "$keystore" --password-file "$passfile")"
  pre_nonce=$(( $(get_nonce "$deployer_address") ))

  # Same balance >= gas_limit * gas_price preflight the node itself enforces
  # (see the DEFAULT_GAS_LIMIT comment above) -- checked here, before forge
  # even runs, so an underfunded wallet gets one precise, actionable error
  # instead of depending on forge's own preflight message wording.
  gas_limit_value=""
  for i in "${!forge_args[@]}"; do
    if [[ "${forge_args[$i]}" == "--gas-limit" ]]; then
      gas_limit_value="${forge_args[$((i+1))]}"
      break
    fi
  done
  [[ -z "$gas_limit_value" ]] && gas_limit_value="${ETH_GAS_LIMIT:-$DEFAULT_GAS_LIMIT}"

  balance_wei=$(( $(get_balance "$deployer_address") ))
  gas_price_wei=$(( $(get_gas_price) ))
  required_wei=$(( gas_limit_value * gas_price_wei ))
  if (( balance_wei < required_wei )); then
    die 7 "deployer $deployer_address has balance $balance_wei wei, but broadcasting needs >= $required_wei wei ($gas_limit_value gas x $gas_price_wei wei/gas at the current gas price) -- top up the wallet or lower --gas-limit"
  fi
fi

set +e
forge "$mode" "${forge_args[@]}" \
  --rpc-url "$rpc_url" \
  --rpc-headers "$rpc_headers" \
  --keystore "$keystore" \
  --password-file "$passfile"
forge_exit=$?
set -e

if ! $broadcasting; then
  exit "$forge_exit"
fi

# forge's own exit code/message is not reliable evidence of success OR
# failure for a --broadcast run on this gateway (see references/pro-api-auth.md
# -- "False-negative forge create --broadcast failure"). Verify against the
# chain via the Blockscout PRO API instead of trusting it either way.
echo >&2
echo "Verifying broadcast result via the Blockscout PRO API (forge's own exit code was $forge_exit -- not treated as authoritative)..." >&2

post_nonce="$pre_nonce"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  post_nonce=$(( $(get_nonce "$deployer_address") ))
  [[ "$post_nonce" -gt "$pre_nonce" ]] && break
  sleep 3
done

if [[ "$post_nonce" -le "$pre_nonce" ]]; then
  echo "error: no new transaction was mined from $deployer_address -- nothing was broadcast; forge's exit code ($forge_exit) is the only signal available" >&2
  exit "$forge_exit"
fi

verified=false
final_ok=true
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  txs_json="$(curl -s --request GET \
    --url "https://api.blockscout.com/${chain_id}/api/v2/addresses/${deployer_address}/transactions?items_count=50" \
    "${rest_headers[@]}")"

  pass_all_found=true
  lines=()
  ok_this_pass=true
  for (( n=pre_nonce; n<post_nonce; n++ )); do
    item="$(echo "$txs_json" | jq -c --argjson n "$n" '[.items[]? | select(.nonce == $n)] | first // empty')"
    if [[ -z "$item" || "$item" == "null" ]]; then
      pass_all_found=false
      break
    fi
    # A tx can appear in this list before Blockscout has resolved its final
    # outcome -- result stays "pending" and status stays null in that
    # window (confirmed empirically: observed ~20-30s after the tx was
    # already mined). Treat that exactly like "not found yet" -- i.e. keep
    # retrying the whole pass -- rather than reading the unresolved null as
    # a failure. Getting this wrong once already produced a false FAILED on
    # a deployment that had, in fact, succeeded.
    item_result="$(echo "$item" | jq -r '.result // empty')"
    tx_status="$(echo "$item" | jq -r '.status // empty')"
    if [[ -z "$item_result" || "$item_result" == "pending" || -z "$tx_status" ]]; then
      pass_all_found=false
      break
    fi
    hash="$(echo "$item" | jq -r '.hash')"
    created="$(echo "$item" | jq -r '.created_contract.hash // empty')"
    if [[ "$tx_status" == "ok" ]]; then
      if [[ -n "$created" ]]; then
        lines+=("Verified: nonce $n, tx $hash -- SUCCESS, contract created at $created")
      else
        lines+=("Verified: nonce $n, tx $hash -- SUCCESS")
      fi
    else
      lines+=("Verified: nonce $n, tx $hash -- FAILED (status=$tx_status)")
      ok_this_pass=false
    fi
  done

  if $pass_all_found; then
    verified=true
    final_ok=$ok_this_pass
    for l in "${lines[@]}"; do echo "$l" >&2; done
    break
  fi
  sleep 5
done

if ! $verified; then
  die 6 "transaction(s) mined (nonce $pre_nonce..$((post_nonce - 1)) from $deployer_address) but Blockscout hadn't resolved their final status after ~60s of retrying -- check manually via the Blockscout MCP tools before concluding success or failure"
fi

[[ "$final_ok" == true ]] && exit 0 || exit 1
