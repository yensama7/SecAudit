# Solidity audit checklist

Work this per in-scope contract. It's a prompt list, not a scoreboard — a "no"
that's actually exploitable becomes a finding; a "no" that's mitigated or
unreachable does not.

## Per contract
- [ ] What does it do, and what are its invariants? Write them down.
- [ ] Entry points: every `external`/`public` state-changing function listed.
- [ ] Roles: owner/admin/minter/etc. and exactly what each can do.
- [ ] Funds: every path that moves ETH or tokens in/out.
- [ ] External dependencies: which other contracts it calls/trusts.

## Access control
- [ ] Every fund-moving / role-changing fn has the correct modifier.
- [ ] Initializer protected and not re-callable; impl contract disabled.
- [ ] No `tx.origin` auth. Ownership transfer is 2-step or justified.
- [ ] Privileged setters bounded (fees capped, addresses non-zero).

## Reentrancy
- [ ] CEI order on every fn with an external call, OR `nonReentrant`.
- [ ] Guard covers all functions sharing the same state (cross-fn).
- [ ] No read-only reentrancy exposure to external integrators.
- [ ] Token hooks (ERC777/721 `onReceived`) considered.

## Arithmetic
- [ ] Multiply-before-divide where precision matters.
- [ ] Rounding direction favors protocol, not attacker; not farmable.
- [ ] Casts don't truncate attacker-controlled values.
- [ ] 4626/share math safe against first-depositor inflation (dead shares/virtual).
- [ ] `unchecked` blocks can't actually overflow.

## Oracles / pricing
- [ ] Not using AMM spot price as the source of truth.
- [ ] Chainlink: checks `updatedAt` staleness, L2 sequencer uptime, `answeredInRound`.
- [ ] Price sanity bounds; no silent 0 / stale consumption.

## Accounting / tokens
- [ ] SafeERC20 for transfer/approve (handles non-bool returns).
- [ ] Doesn't trust `balanceOf(this)` where direct transfers are possible.
- [ ] Fee-on-transfer / rebasing handled or declared out of scope.
- [ ] Shares minted only after assets received.

## Signatures
- [ ] Nonce per signer; chainId + verifying contract in signed payload.
- [ ] `ecrecover` zero-address and malleability handled (prefer OZ ECDSA).

## DoS / gas
- [ ] No unbounded loops over user-growable arrays on a critical path.
- [ ] One recipient's revert can't brick everyone (pull over push).
- [ ] Funds never permanently stuck.

## Upgradeability
- [ ] Storage layout stable; `__gap`; no `delegatecall` to untrusted impl.

## MEV
- [ ] Swaps/withdrawals have slippage + deadline the user controls.
- [ ] Front-runnable first-depositor / liquidation / init protected.

## Coverage
- [ ] Mark this file `examined` in coverage.json with any unresolved questions.
