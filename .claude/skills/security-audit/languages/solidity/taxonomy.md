# Solidity / EVM vulnerability taxonomy

Investigation categories. A category is a place to *look*, not a verdict. For
each, the questions tell you what to check in the actual code.

## 1. Access control & authorization
Who can call state-changing / fund-moving functions? Is every privileged
function gated? Right modifier on the right function? `tx.origin` used for auth?
Role granted but never revoked? Initializer callable twice? Ownership transfer
one-step (can be set to a wrong/zero address)? Missing check that an address is
the *expected* contract.

## 2. Reentrancy & external-call ordering
Any state read/written AFTER an external call (`.call`, `.transfer`, token
transfer, callback, ERC777/ERC721 hooks)? Follows Checks-Effects-Interactions?
Is `nonReentrant` present AND on every entry that shares the state?
Cross-function and cross-contract reentrancy (guard on A but not B touching the
same state)? Read-only reentrancy (a view used by another protocol returns stale
values mid-call)?

## 3. Arithmetic, precision & rounding
Division before multiplication (precision loss)? Rounding direction — does it
favor the protocol or the attacker? Can rounding be repeated for profit? Unchecked
blocks hiding overflow? Casting down (`uint256`->`uint128`) truncation?
Share/asset conversion (ERC4626-style) inflation attack via first depositor?
Fixed-point mismatch (1e18 vs token decimals)?

## 4. Oracle & price manipulation
Spot price from an AMM used as an oracle (flash-loan manipulable)? Single oracle,
no sanity bounds / staleness / sequencer check? `latestAnswer` without checking
`updatedAt` / `answeredInRound`? LP token priced naively? TWAP window too short?

## 5. Accounting & balance inconsistencies
Does internal accounting track real balances? `balanceOf(this)` trusted when
tokens can be sent directly (donation / inflation)? Fee-on-transfer or rebasing
token breaks "amount received == amount sent"? Double-counting? Shares minted
before assets pulled?

## 6. Signature verification & replay
ECDSA: zero-address on bad sig? Malleability (s-value / `ecrecover`)? Nonce per
signer? Replay across chains (no chainId in the signed data)? Replay across
contracts? EIP-712 domain correct? Signature reused across functions?

## 7. Initialization & upgradeability
Proxy: initializer protected (`initializer`/`_disableInitializers`)? Storage
layout collision across upgrades? `delegatecall` to attacker-controlled impl?
Uninitialized implementation contract self-destructible? Constructor logic that
should be in initializer for proxies? `__gap` present?

## 8. Denial of service & gas
Unbounded loop over user-growable array (push to block)? External call in a loop
where one revert bricks everyone? Funds stuck if a receiver reverts? Griefable
via dust? Fixed-gas `.transfer` to a contract that needs more? Pull-over-push
violated?

## 9. Token-behavior assumptions
Assumes ERC20 returns bool (USDT doesn't) — must use SafeERC20? Assumes 18
decimals? Assumes no transfer fee? Assumes no reentrancy on transfer (ERC777)?
Approve race (not using increase/decrease)? Non-standard tokens in scope?

## 10. State-transition & invariant violations
Can a function be called in the wrong order/phase? Missing state check lets you
e.g. withdraw before deposit settles, claim twice, liquidate a healthy position,
bypass a timelock? Enumerate the protocol invariants and attack each.

## 11. MEV / front-running / sandwich
Slippage / deadline params missing or defaulted? Commit-reveal needed? Can a
searcher front-run a profitable action (liquidation, first-depositor, price
update)? Sandwichable swaps?

## 12. Low-level & misc
`delegatecall` target control; `selfdestruct`; assembly memory safety;
`abi.encodePacked` hash collisions with dynamic types; `block.timestamp`
dependence for randomness; `create2` address assumptions; return-data bombs.
