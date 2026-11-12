# Reentrancy — what to look for

### State-changing function relies on the caller for reentrancy protection
- **Look for:** a function that makes an external call mid-execution (e.g.
  `depositToUnderlying(...)`, a token transfer, a callback to an integrated
  protocol) and then updates state, but has **no** `nonReentrant` guard of its
  own because it "trusts" the only authorized caller (a controller/router) to
  guard. Watch for guards placed on the *wrong* functions (owner-only, CEI-safe
  ones) while the genuinely exposed one is unguarded. The injected caller may be
  swapped later (versioned/non-upgradeable), so the assumption silently breaks.
- **Root cause:** reentrancy protection delegated to an external caller instead
  of enforced locally; the protected invariant depends on deployment wiring, not
  on the contract itself.
- **How it's fixed:** each contract protects its own entry points
  (`nonReentrant` on the exposed, external-call-bearing function) and follows
  checks-effects-interactions — never rely on the outside caller to hold the lock.
- **Languages:** solidity
- **Typical severity:** low–high (depends on reachability; here low because the
  current controller happened to guard, but flagged as a future-deployment trap)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.02.09%20-%20Final%20-%20Tempus%20Audit%20Report.pdf

### Cross-contract / cross-function reentrancy that per-function `nonReentrant` misses
- **Look for:** two state-changing functions in **different contracts** that each
  have their own `nonReentrant` guard (so they *look* safe), but one makes an
  external call (token transfer, callback) that can re-enter the *other*. The
  separate guards don't share a lock, so A-calls-out → attacker calls B. Classic
  tell: a loop that takes an **in-memory snapshot** of a position/balance at the
  start of an iteration, then makes an external call mid-iteration — the attacker
  mutates the real storage (e.g. `split`s the position) while the stale snapshot
  is still used to pay out, then the original is burned at the end → double spend.
- **Root cause:** reentrancy reasoned about per-function, not across the call
  graph; CEI violated because value is sent before the position is burned/updated;
  a memory copy diverges from storage across an external call.
- **How it's fixed:** apply CEI regardless of guards — burn/update state **before**
  any external transfer; use a shared reentrancy lock across the related contracts;
  don't trust a pre-call memory snapshot after control may have left the contract.
  Treat upgradeable/"trusted" tokens as potential reentrancy sources.
- **Languages:** solidity
- **Typical severity:** high when reachable (fund drain); here medium because the
  only external token was a trusted (but upgradeable) Synthetix asset
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.27%20-%20Final%20-%20Lyra%20Audit%20Report.pdf

### Read-only reentrancy: state counter updated *after* the external mint/transfer callback
- **Look for:** an ERC1155 `_mint` (or ERC721 `_safeMint`) followed by a state
  update that integrators read — e.g. `supply += amount` incremented **after**
  `_mint(to, tokenId, amount, "")`, or any `totalAssets`/`balanceOf` accounting
  updated after a transfer that calls a callback (`onERC1155Received`,
  `onERC721Received`). During the callback the recipient can call back into
  **other contracts** that read `tokenMetadata[tokenId].supply` (or any stale
  getter) to price/value the token — they see a supply that is too low (the
  mint happened but the counter didn't). The BondFixedTermTeller contract itself
  isn't drained, but an **integrator** relying on the stale supply for pricing
  is. Same class appears any time `totalAssets` or a checkpoint is updated after
  a hook-triggering transfer.
  Also: an **external protocol** (Curve, Balancer) whose liquidity-removal function
  sends native ETH to the caller's `receive()` **before** completing its own internal
  token-balance accounting (e.g. Curve `remove_liquidity` sends ETH first, then
  adjusts pool state) — during this callback window, view functions like
  `get_virtual_price()` return a transiently wrong suppressed value. Any integrating
  protocol that reads such a view to price collateral or trigger liquidations during a
  user-controlled callback inherits the manipulation without itself having a reentrancy
  bug. Tell: collateral priced as `get_virtual_price() * coinPrice`, reached from a
  user-triggered callback inside a Curve/Balancer withdrawal.
- **Root cause:** CEI violation: the external call (token mint/transfer, or Curve's
  ETH send) happens before the state it's supposed to reflect is updated, so the
  callback window sees inconsistent storage. No guard can help if the inconsistency
  is *read* from another contract — only ordering fixes it.
- **How it's fixed:** apply strict CEI at the storage layer: update all counters
  (`supply`, `totalAssets`, checkpoints) **before** calling `_mint`/`_transfer`;
  for the Curve external variant: add a no-op reentrancy probe call
  (`pool.remove_liquidity(0, [0,0])`) before reading `get_virtual_price()` — this
  triggers the pool's own reentrancy guard if the pool is currently in a callback
  and reverts cleanly; or use a Chainlink-backed LP price feed instead of `virtual_price`.
- **Languages:** solidity
- **Typical severity:** medium (integrators see mispriced state; direct loss
  depends on what they do with it; Curve variant allows forced liquidations)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.29%20-%20Final%20-%20Bond%20Protocol%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Sentiment%20December%20Update%20Audit%20Report.pdf (H-1: wstETH-ETH Curve LP priced via `get_virtual_price()`; `remove_liquidity` sends ETH to attacker's `receive()` before updating pool's wstETH balance → `virtual_price` suppressed by up to 43% during the callback → attacker calls Sentiment's `liquidate()` from `receive()` to force unfair liquidations on normally-safe accounts)

### Token-transfer callback (ERC777/ERC677) re-enters code that assumed plain ERC20
- **Look for:** a function that `safeTransfer`s a user-chosen token and then
  continues (updates balances, deletes the asset list, runs a health check) with
  **no** `nonReentrant` guard, because the authors assumed every token is a
  passive ERC20. If the token can be an **ERC777** (e.g. imBTC) or ERC677 — i.e.
  it calls `tokensReceived`/a recipient hook on transfer — the recipient re-enters
  mid-function. Classic sink: a `sweepTo`/`closeAccount`/withdraw loop that sends
  each asset in turn; the hook fires during one transfer and the attacker re-opens
  the account, deposits, and **borrows with no health check** (the check runs only
  after the loop), then the loop finishes paying everything out → account drained
  with a bad-debt balance. Enabler is often a second bug that lets an arbitrary
  (hook-bearing) token into the asset list in the first place.
- **Root cause:** "it's an ERC20, transfers can't call back" — but hook tokens do;
  state the post-loop invariant depends on is mutated during the external call,
  violating checks-effects-interactions across the whole function.
- **How it's fixed:** add a `nonReentrant` guard on the entry points (not just
  per-leaf), apply CEI so all state/health checks settle before any transfer, and
  restrict which tokens can enter the system (reject/escrow hook-bearing tokens,
  or treat every token as potentially re-entrant).
- **Languages:** solidity
- **Typical severity:** high–critical (full pool drain via borrowed, unbacked funds)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (malicious lien owner re-enters the auction flow to have liens removed without paying) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.16%20-%20Final%20-%20NFTPort%20Audit%20Report.pdf (ERC721 `_safeMint` → `onERC721Received` callback re-enters `mint()` before the per-tx `tokensPerMint` counter resets, bypassing the limit) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20BullvBear%20Audit%20Report.pdf (H-4: `withdrawToken()` has no `nonReentrant` guard — ERC721 `safeTransferFrom` → `onERC721Received` → re-enters `settleContract()` to overwrite `withdrawableCollectionTokenId`, then `withdrawToken` zeros it out, locking the NFT forever)
