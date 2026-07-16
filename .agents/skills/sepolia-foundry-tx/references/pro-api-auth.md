# Blockscout PRO API JSON-RPC gateway — how this was verified

Background material for `SKILL.md`. Read this when you need to double-check
the approach still holds (e.g. after a Blockscout PRO API change), justify
it to someone, or re-derive it from scratch. Day-to-day deployment work
should not need this file — `SKILL.md` and `scripts/deploy.sh` are enough.

## The gateway is a real JSON-RPC proxy, not just `eth_call`

The PRO API's own skill documentation (`agent-skills/web3-dev/SKILL.md`)
only advertises `eth_call` for `https://api.blockscout.com/{chain_id}/json-rpc`.
Whether write methods are also proxied was confirmed empirically, not
assumed, against the live Sepolia gateway (`chain_id=11155111`):

| Call | Result | Reading |
|---|---|---|
| `eth_chainId` | `{"result":"0xaa36a7"}` | `0xaa36a7` = 11155111 — gateway reachable, correctly scoped to Sepolia |
| `eth_getTransactionCount` | `{"result":"0x0"}` | a second read method beyond `eth_call` also works |
| `eth_sendRawTransaction` with payload `"0xdeadbeef"` (garbage, not valid RLP) | `{"error":{"code":-32000,"message":"Invalid RLP."}}` | **structured JSON-RPC error** — the request reached real transaction-decoding logic |
| `eth_totallyMadeUpMethod` (control: genuinely unsupported method) | `{"error":"Action not found."}` | a plain string, not a JSON-RPC error object |

The distinguishing signal is the **shape** of the error, not just its
presence: a recognized-but-rejected method returns a structured JSON-RPC
error object (`{"code":..., "message":...}`); a method the gateway doesn't
know about at all returns the flatter `{"error": "Action not found."}`
shape. `eth_sendRawTransaction` produced the former, meaning the gateway has
it in its allow-list and routes it through to real decode logic — it just
rejected our deliberately-invalid payload, as it should.

**To re-verify after a Blockscout API change:** send the write method you
care about with an obviously-invalid payload and compare the error shape
against a control call using a method name you make up. If the real method's
error is a structured JSON-RPC error and the made-up method's error is the
flat "Action not found" string, the real method is still proxied. This never
risks an actual broadcast, since the payload is invalid by construction.

## Authentication: header vs. query parameter

Both work against the gateway — verified directly:

| Call | Result |
|---|---|
| `Authorization: Bearer <valid key>` (header) | success |
| `?apikey=<valid key>` (query param) | success, `x-credits-remaining` present |
| no auth at all | `{"error":"Proceed with API key or make a X402 payment to continue"}` |
| `?apikey=<garbage>` | `{"error":"Unauthorized"}` |

`SKILL.md` and `scripts/deploy.sh` use the **header** exclusively. Reasoning:

1. **Logging exposure.** Secrets embedded in a URL end up in the places that
   log or echo full URLs by default — proxy/CDN access logs, verbose tool
   tracing (Foundry's `-vvvv`), and error messages that print the failing
   endpoint (`"failed to reach <url>"`). Headers are conventionally excluded
   from that kind of logging. Since `forge`'s own error output is exactly
   the kind of diagnostic this skill relies on being safe to read and show
   the user, keeping the secret out of anything likely to be echoed matters
   more here than it might elsewhere.
2. **Separation of concerns.** With the header, the RPC URL itself stays
   secret-free and reusable as plain configuration; with the query param,
   every place the URL is written down (a script variable, a config file, a
   command's `--rpc-url` value) carries the key.
3. **Consistency.** The rest of this project's PRO API usage (REST calls,
   `web3-dev` skill examples) already uses `Authorization: Bearer` as the
   only authentication scheme. Using the header here avoids introducing a
   second, project-inconsistent method for the same underlying API.

Foundry supports attaching the header via `--rpc-headers <HEADER>` (env
`ETH_RPC_HEADERS`) on both `cast` and `forge` — confirmed present in this
project's Foundry version (1.7.1) via `cast send --help` / `forge script
--help`.

## Gas and fee estimation gaps (why `scripts/deploy.sh` defaults `--gas-limit` and `--legacy`)

Discovered by actually running `forge create` against the gateway (dry run,
nothing broadcast) and reading what failed at each step:

1. **No `--gas-limit`**: forge calls `eth_estimateGas` with a contract-creation
   shaped request (no `to` field — the standard way to represent "this call
   creates a contract" in the Ethereum JSON-RPC spec). The gateway rejects
   this outright:
   ```
   eth_estimateGas [{"from":"...","data":"0x..."}]        -> {"error":"Incorrect number of params."}
   eth_call        [{"from":"...","data":"0x..."}, "latest"] -> {"error":"Missed `to` address"}
   ```
   The gateway requires a `to` field even for calls that are, by definition,
   creating a contract that doesn't have an address yet. There's no
   workaround on the caller's side other than skipping estimation entirely —
   hence `--gas-limit <value>` supplied explicitly.

2. **Default EIP-1559 fee estimation**: without `--legacy`, forge fails with
   `Failed to estimate EIP1559 fees. This chain might not support EIP1559,
   try adding --legacy to your command` (forge's own error, and it names the
   right fix). The specific gap:
   ```
   eth_gasPrice              -> works
   eth_maxPriorityFeePerGas  -> works
   eth_feeHistory            -> {"error":"Action not found."}
   ```
   Foundry's EIP-1559 fee oracle needs `eth_feeHistory`, which the gateway
   doesn't expose, even though the two other fee-related methods do work.
   `--legacy` switches forge to the single-`gasPrice` model (`eth_gasPrice`
   only), which the gateway supports — confirmed end-to-end: with both
   `--gas-limit 3000000 --legacy`, a full dry-run transaction (correct
   `from`, `nonce`, `chainId`, compiled bytecode as `input`) was produced
   with no errors.

`scripts/deploy.sh` applies `--gas-limit 2500000` and `--legacy`
automatically unless the caller already passed one, rather than requiring
every invocation to specify them. Gas is billed by actual usage, not by the
limit, so a generous default costs nothing extra *in fees* — but the node
still requires the account's balance to cover `limit × gasPrice` just to
accept the transaction (an "InsufficientFunds" preflight check, independent
of what the transaction would actually end up costing). This was originally
defaulted to 5,000,000 and that turned out to be a real mistake, not just a
theoretical one: on a wallet topped up in small increments (0.01 ETH at a
time, not a one-time large faucet grant), two prior deployments left only
~0.0049 ETH — enough to actually pay for a third deployment (~0.0025 ETH)
but *not* enough to satisfy a 5,000,000-gas-limit preflight check
(~0.0064 ETH required) — so `--broadcast` failed before ever reaching the
chain, with `deploy.sh` correctly reporting forge's own (real, non-false)
`InsufficientFunds` error and falling back to forge's exit code, since
nothing had been broadcast to verify. The default is now 2,500,000 —
confirmed sufficient with margin for `Web3PyTestContract.sol`'s actual usage
of 1,963,456 gas, while reserving roughly a third less balance than the
former default for the preflight check. This is a real, recurring trade-off
for any test wallet funded in small increments, not a one-time fix: override
`--gas-limit` downward if `InsufficientFunds` recurs on a low balance, or
top up the wallet.

**Dry runs do not validate the gas limit is sufficient.** Tested directly:
a dry run (no `--broadcast`) with a deliberately too-low `--gas-limit 21000`
produced a clean, error-free simulated transaction, identical in shape to
one with an adequate limit — forge builds the transaction it would send
without checking whether that gas would actually be enough. Whether an
insufficient-but-plausible gas limit (as opposed to a limit clearly below
the intrinsic minimum) shows up as a distinct error at all after a real
`--broadcast` was not conclusively separated from the false-negative
failure mode below — see that section for why the practical guidance is the
same either way: verify on-chain, don't trust forge's message.

Both gaps are about the gateway's RPC surface, not about `scripts/deploy.sh`
or Foundry being misconfigured — re-verify with the raw `curl` calls above
(swap in the contract's actual `from`/`data`) if this ever needs rechecking
after a Blockscout PRO API change.

## False-negative `forge create --broadcast` failure

Discovered while testing an actual deployment end-to-end (not a dry run):
`forge create` reported `Error: contract was not deployed` (exit 1, no
further detail even with `-vvvv`) on **two separate real broadcasts**
through this gateway — and both had, in fact, succeeded. Verified
independently via the Blockscout MCP tools, not by trusting forge:

| Tx hash | Nonce | Deployed contract | Gas used | On-chain status |
|---|---|---|---|---|
| `0x9070fc7e4f5bf7d79e999f4d3b6a6ec1d8a664c758f39264af659588dc9fddd8` | 0 | `0x75274acBca1bc9024E233579e3F6F2D49373288d` | 1,963,456 | `status: success`, `creation_status: success`, `is_contract: true` |
| `0x5c6ac35f3c88ad4611dfd8052a25ca3b1cfbb54a9098b3b80b03855e6fb3642c` | 1 | `0x44aBd82d4a1D1027371C7a242F6BD07585ee2678` | 1,963,456 | same |

The second deployment only happened because the first one's (false) failure
led to a retry — a real, if cheap, cost of trusting forge's report at face
value on this gateway. Both were confirmed via `get_transaction_info` (both
show `transaction_types: ["contract_creation"]`, `result: success`) and
`get_address_info` on both created addresses (both `is_contract: true`,
`creation_status: success`, `creation_transaction_hash` matching exactly).

**Likely root cause (inferred, not independently isolated further):** forge
polls for the transaction receipt after broadcasting and checks it locally
to confirm contract creation before reporting success — this almost always
means reading `receipt.contractAddress`. The identical, generic error on
both runs (rather than a timeout or network error) suggests the gateway's
receipt for a contract-creation transaction doesn't have that field in the
shape forge's client expects, so forge concludes failure regardless of the
actual on-chain outcome. This was not confirmed by directly inspecting a raw
`eth_getTransactionReceipt` response for one of these transactions — doing
so would be the next step to fully close this out, comparing its shape
against what forge/alloy expects.

**Practical consequence:** treat `forge create`/`forge script --broadcast`'s
own exit code and message as unreliable on this gateway, in both directions.
The only reliable signal is the on-chain state itself.

**Why `scripts/deploy.sh` now verifies this automatically, and why via REST
rather than raw JSON-RPC:** relying on "the agent remembers to double-check"
is exactly the kind of instruction that's easy to skip under time pressure —
which is literally how the second, redundant contract above got deployed.
So the script now does it unconditionally after every `--broadcast` run:
capture the deployer's nonce before and after (via `eth_getTransactionCount`
on the json-rpc gateway — a plain counter, unaffected by the receipt gap),
then look up each transaction in that nonce range via the PRO API's indexed
REST endpoint, `GET /{chain_id}/api/v2/addresses/{address}/transactions`.
REST, not another raw JSON-RPC call, is the deliberate choice here — the raw
gateway's receipt is the very thing suspected of being malformed for
contract-creation transactions (previous section), so re-querying that same
surface (e.g. `eth_getTransactionReceipt`) could plausibly hit the identical
gap. Blockscout's own indexer has to correctly resolve a created contract's
address to render its explorer pages at all, so the indexed REST view is
good independent evidence regardless of what the raw gateway's receipt looks
like — confirmed directly: the REST lookup correctly showed
`created_contract.hash` and `status: "ok"` for both transactions in the
table above, matching the Blockscout MCP tool results exactly.

## A second false-negative — this time in `scripts/deploy.sh`'s own verification

The REST-based verification described above was, on its first real
end-to-end test with the current script, itself caught producing a false
`FAILED` — the exact class of bug it exists to eliminate, just relocated
from forge's exit code into the wrapper's own polling logic. Worth recording
in as much detail as the original bug, since it's the same lesson applied
one layer deeper.

**What happened:** a real `--broadcast` deployment succeeded on-chain (tx
`0x6f59a957cae14b8eab162696ec797f263ba644c4683c18b0134a10f5ac872647`, nonce
2, contract `0x0d7f63f0e91C9e0fDa14A350787D85c80DC7bB30`, `gas_used:
1963456` — identical usage to every other deployment of this contract).
`scripts/deploy.sh` printed `Verified: nonce 2, tx 0x6f59a9... -- FAILED
(status=unknown)` and exited `1`. Independently checked via
`get_transaction_info` immediately after the script finished: `result:
"pending"`, `status: null`, `block_number: null`. Polling again ~20–30s
later, the same transaction showed `status: "ok"`, `result: "success"`.

**Root cause:** the verification loop's retry logic (at the time) only
retried when a transaction was *entirely absent* from the indexed
`/addresses/{address}/transactions` list. The instant the transaction
appeared in that list at all — even mid-resolution, with `result: "pending"`
and `status: null` — the loop treated that single snapshot as final.
`jq -r '.status // "unknown"'` turned the `null` into the literal string
`"unknown"`, which fails the `== "ok"` check and was scored as a hard
`FAILED`, with no further retries. So there were, in effect, two different
"not ready yet" states the loop needed to treat identically — "not in the
list yet" and "in the list but not yet resolved" — and it only handled the
first one.

**Fix:** the per-transaction check now also treats `result == "pending"` (or
a missing/empty `result` or `status`) as "not found yet," which falls
through to the same outer retry loop as an absent transaction, rather than
being scored as a failure on the spot. The retry budget was also widened
(from 5×3s ≈ 15s to 12×5s ≈ 60s) to comfortably cover the ~20–30s resolution
delay observed directly. Re-tested afterward with a fresh real deployment
(tx `0x671fb7aa8303a6d4d629a73fbb768bf911e9c5c04aae06e356fd659426980848`,
nonce 3): forge again printed the false-negative `Error: contract was not
deployed`, but the script's own output now correctly read `Verified: nonce
3, tx 0x671fb7... -- SUCCESS, contract created at 0xDe9a842f...`, exit `0`
— independently confirmed via a direct PRO API REST call
(`result: "success"`, `status: "ok"`, `gas_used: 1963456`,
`created_contract: 0xDe9a842f978ddF61Cf9D38DB4e47Dc77a74DebDe`, matching
exactly).

**The generalizable lesson, not specific to this gateway:** when polling any
indexer/explorer API for a transaction's outcome, "present in a list" and
"has a final, resolved status" are two different conditions, and an
in-between state (`pending`/`null`) is common enough to hit on the first
poll after a transaction is mined. Code that checks a status field without
first checking whether that field has actually been populated will read
`null` as whatever its fallback default happens to be — here, a string that
looked enough like a real (bad) status to be trusted.

## `cast wallet address` doesn't always read `CAST_PASSWORD` non-interactively

Creating a key (`cast wallet new .ai/wallet <name>`) accepts `CAST_PASSWORD`
as an env var fine. But manually inspecting an *existing* keystore this way —
`CAST_PASSWORD="$(cat <name>.pass)" cast wallet address --keystore <name>` —
failed in a sandboxed shell with `Error: Device not configured (os error 6)`,
as if it were trying to prompt interactively for the password and finding no
tty. Confirmed empirically while testing this skill end-to-end.
`--password-file <name>.pass` (what `scripts/deploy.sh` itself always uses
internally) worked immediately in the same environment. Not investigated
further since the script's own usage was never affected — worth knowing only
if you ever need to run a `cast wallet` subcommand by hand outside the
script.

## Credits and rate limits

Every gateway call (reads and writes alike) is billed against the PRO API's
daily credit allowance and counts against the plan's RPS limit, exactly like
any other PRO API request. See the `web3-dev` skill for the full model
(`/api/json/plans`, `/api/json/config`, the `x-credits-remaining` response
header). Nothing about sending a transaction through this gateway is billed
or rate-limited differently from a read call.
