---
name: sepolia-foundry-tx
description: >
  Use this skill whenever the agent needs to deploy a smart contract to
  Sepolia testnet via Foundry (`forge create` or `forge script --broadcast`),
  routed through the Blockscout PRO API's JSON-RPC gateway instead of a
  third-party RPC provider. Trigger on requests like "deploy this contract to
  Sepolia", "deploy via Foundry", "broadcast this Foundry deployment
  script", or any `forge create`/`forge script` invocation that needs a
  signer and an RPC endpoint for Sepolia (chain id 11155111) in this
  project. Also consult it to find which local Foundry keystore to sign
  with — this project stores test signing keys as encrypted keystores
  under `.ai/wallet/`, never as a plain private key in `.env`. Do not use
  this for reads (balances, transaction history, contract info) — use the
  connected Blockscout MCP tools for those directly; this skill is
  specifically about broadcasting a deployment.
---

# Deploying contracts to Sepolia via Foundry + Blockscout PRO API

## What this is for

Deploying a contract needs three ingredients: an RPC endpoint that accepts
the broadcast, credentials for it, and a signer. This project gets all three
without a third-party RPC provider — the Blockscout PRO API's JSON-RPC
gateway, authenticated with the project's existing `BLOCKSCOUT_PRO_API_KEY`,
and a local encrypted Foundry keystore. `scripts/deploy.sh` wires these
together and runs the real `forge create`/`forge script` command.

## Creating a signing key

If `.ai/wallet/` has no keystore yet (the script will `die` saying so),
create one — an encrypted Foundry keystore, never a plain private key in
`.env`:

```bash
mkdir -p .ai/wallet
openssl rand -base64 32 | tr -d '\n' > .ai/wallet/<name>.pass && chmod 600 .ai/wallet/<name>.pass
CAST_PASSWORD="$(cat .ai/wallet/<name>.pass)" cast wallet new .ai/wallet <name> && chmod 600 ".ai/wallet/<name>"
```

Report the resulting address to the user so they can fund it with Sepolia
testnet ETH — the script checks the balance itself before broadcasting and
will refuse with a clear error if it isn't enough (see [Reading the
script's output](#reading-the-scripts-output)).

## Quick start

```bash
.agents/skills/sepolia-foundry-tx/scripts/deploy.sh <create|script> [--key-name NAME] [--chain-id ID] -- <forge args...>
```

The script auto-adds `--gas-limit 2500000` and `--legacy` because the
gateway can't estimate contract-creation gas or EIP-1559 fees (full
rationale in [Background](#background--how-this-was-verified)) — you rarely
need to touch these. Override `--gas-limit` for an unusually large contract,
an out-of-gas revert, or an "InsufficientFunds" error on a lightly-funded
wallet — lowering the limit can resolve that (see Background for why).

**Simulate first (no `--broadcast`) to catch problems for free** — forge
only broadcasts when `--broadcast` is present in the forwarded args, so
omitting it is a safe dry run. Note this only catches compile errors and
malformed args, not an insufficient gas limit — the simulation doesn't
validate that:

```bash
.agents/skills/sepolia-foundry-tx/scripts/deploy.sh create -- src/MyToken.sol:MyToken --constructor-args "Foo" "FOO"
```

Once that looks right and the user has confirmed (see [Safety](#safety)),
add `--broadcast` to actually send it:

```bash
.agents/skills/sepolia-foundry-tx/scripts/deploy.sh create -- src/MyToken.sol:MyToken --constructor-args "Foo" "FOO" --broadcast
```

For a scripted, multi-step deployment (`forge script`):

```bash
.agents/skills/sepolia-foundry-tx/scripts/deploy.sh script -- script/Deploy.s.sol --broadcast
```

Everything after `--` is forwarded to `forge` verbatim — pass whatever
`forge create`/`forge script` flags the deployment needs
(`--constructor-args`, `--verify`, etc.).

## Reading the script's output

**Before `--broadcast`** (a dry run, or any wrapper-detected problem): the
output is trustworthy as-is. Wrapper problems (`error: ...` — see the
script's header comment for the exact exit codes) and forge's own
pre-broadcast errors (compile failures, bad args) are both directly
actionable. One to know: if `.ai/wallet/` has more than one keystore, the
script asks for `--key-name` — don't pick one yourself; ask the user which
key to use.

**After `--broadcast`, trust the script's exit code and its `Verified:`
lines, not forge's own output** — forge's success/failure check is
unreliable on this gateway (see
[Background](#background--how-this-was-verified)). Exit `6` means mined but
not yet resolved: inconclusive, check manually rather than retrying; any
other nonzero exit is a genuine on-chain failure. See the script header for
the full exit-code table.

## Safety

- This setup is for a **Sepolia testnet** key with no real economic value.
  Even so, confirm with the user before running the script *with*
  `--broadcast` — broadcasting a deployment is not reversible the way a
  simulation or a read is.
- Never widen this to a mainnet chain id (via `--chain-id`) unless the user
  explicitly asks for that; treat it as a new decision, not a copy-paste of
  the default.
- Don't broadcast a retry based on forge's error text, or on an inconclusive
  exit `6` — verify on-chain first either way.

## Background / how this was verified

`references/pro-api-auth.md` has the supporting evidence behind this
skill's choices — gateway write-method support, the auth-method rationale,
the gas/fee-estimation gaps, and both false-negative verification bugs.
Read it only to re-justify or re-verify any of this after a Blockscout API
change; day-to-day deployment work shouldn't need it.
