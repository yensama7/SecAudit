# Accounting / solvency — what to look for

### Total assets diverge from total liabilities (unsocialized bad debt / un-debited fee)
- **Look for:** pooled accounting where a protocol-level total (`product.total`,
  `totalAssets`) and the sum of per-user balances/liabilities are updated on
  different code paths. Two concrete shapes: (a) a fee is subtracted from the
  pool total but never debited from any counterparty, so liabilities exceed
  assets after settlement; (b) bad debt / shortfall from an insolvent or bankrupt
  account is tracked but **not** socialized into withdrawals — early withdrawers
  exit whole, the last ones can't, inviting a bank run.
- **Root cause:** a conserved-quantity invariant (Σ balances == pool total) that
  the code never actually enforces; one side of a transfer/fee is missing, or
  losses aren't proportionally applied to withdrawals.
- **How it's fixed:** debit the counterparty whenever the pool total changes
  (every fee has a payer); on withdrawal from an insolvent pool, apply each
  account's share of the shortfall (e.g. per unit of open position) so no one can
  exit at others' expense. Add an explicit `assets >= liabilities` invariant/test.
- **Languages:** solidity
- **Typical severity:** high (fund loss / insolvency)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.02%20-%20Preliminary%20-%20Perennial%20Audit%20Report.pdf

### Transfer with swapped from/to, or absolute amount instead of the delta
- **Look for:** asset-moving helpers where the argument order or amount is wrong:
  (a) `transferAsset(token, from, to, amt)` called with `msg.sender` as `from`
  and `address(this)` as `to` on a **refund** path (pulls from the user again
  instead of paying them back — funds get double-pulled and stuck); (b) a
  "set collateral/balance **to** X" function that transfers the **full** `X` from
  the user instead of `X - current` (the delta), over-charging them; (c) two
  same-typed params passed in swapped order to an internal fn (e.g.
  `_getLiquidity(total, spot)` vs declared `(spot, total)`) silently corrupting a
  circuit-breaker / threshold check; (d) a function acting on behalf of a
  `_receiver` that reads the **caller's** record instead of the target's
  (`depositsOf[msg.sender][id]` where it should be `depositsOf[_receiver][id]`), so
  the amount minted/credited is computed from the wrong account's position (e.g.
  caller's 4-years-left lock mints 5× the shares the receiver's 10-min lock should).
- **Root cause:** positional-argument, absolute-vs-incremental, and wrong-mapping-key
  mistakes that compile fine (same types) and aren't caught without value-flow tests.
- **How it's fixed:** correct the direction/amount/key (`from = address(this)` on
  refunds; transfer `target - current`; index the record by the account the action
  is *for*); add tests asserting balances before/after for both parties; prefer
  named/struct args over long positional same-type lists.
- **Languages:** solidity
- **Typical severity:** medium–high (direct loss of user funds, over-mint, or DoS of
  a circuit breaker)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.27%20-%20Final%20-%20Lyra%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf (increaseLock reads depositsOf[msg.sender] instead of depositsOf[_receiver]) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.01%20-%20Final%20-%20Frankendao%20Audit%20Report.pdf (H-4: `_unstake` removes votes from `msg.sender` instead of `owner` when third-party calls via approval; H-4 also increments wrong counter: `proposalsCreated` incremented where `proposalsPassed` should be in `queue()`)

### Missing one-to-one / uniqueness invariant lets one backing asset cover many claims
- **Look for:** a system where a unit of collateral/backing (a vaulted NFT, a
  deposit, a position) is supposed to back exactly one instrument, but there's no
  mapping/flag enforcing it — so the same asset can be committed to multiple
  options/loans/claims. At settlement every claimant is paid out or believes they
  won, but only the first to `withdraw` actually gets the asset; the rest lose
  their funds. Tell: a `mint`/`create` that never checks whether an active
  instrument already exists for that `assetId`.
- **Root cause:** an unstated "one backing ↔ one claim" invariant that the code
  never enforces with state.
- **How it's fixed:** track it explicitly — e.g. `mapping(vault => mapping(assetId
  => optionId))`, and require the slot is empty/settled before creating a new
  claim (using id `0` as the "none" sentinel, counter starting at 1).
- **Languages:** solidity
- **Typical severity:** high (claimants lose funds / double-spend of backing)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.30%20-%20Final%20-%20Hook%20Audit%20Report.pdf

### A carved-out reserve is excluded in one accounting path but not the others
- **Look for:** a balance that is meant to be set aside (protocol `reserves`,
  insurance fund, locked/escrowed portion) and is correctly subtracted in **one**
  view (e.g. `totalAssets() = balance + borrows - reserves`, so LPs can't redeem
  it) but is **not** subtracted in the paths that actually spend or rate it: the
  lending/`lendTo` check uses raw `asset.balanceOf(this)` (so the reserve can be
  borrowed out), and the utilization/interest-rate model takes `balanceOf` as
  "liquidity" (so the rate is computed on the wrong base). Tell: `getReserves()`/
  `reserves` referenced in some formulas but a sibling that moves money reads the
  live balance directly.
- **Root cause:** the "this much is reserved" invariant is enforced in the display
  math only; every place that lends, rates, or withdraws must honour the same
  carve-out, and one path forgot.
- **How it's fixed:** gate outflows on `balanceOf - reserves` (e.g.
  `require(balanceOf(this) >= getReserves())` before lending) and feed
  `liquidity - reserves` into the rate model; centralize "available liquidity" in
  one helper used everywhere instead of re-deriving it per call site.
- **Languages:** solidity
- **Typical severity:** medium–high (reserve drained / mispriced interest → insolvency)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf

### Pre-action health/solvency check omits a fee charged by the same action
- **Look for:** a borrow/withdraw/open that runs a health check
  (`isBorrowAllowed`, `isAccountHealthy`) **before** applying a fee that the very
  same action deducts — an `originationFee`, deposit/withdraw fee, or haircut taken
  off the disbursed amount. The check sees the pre-fee position (e.g. "borrow 400,
  collateral fine"), but the user actually receives `400 - fee` while owing 400, so
  the account is **liquidatable the instant the tx lands** (or the check should
  have rejected it). Mirror case: health check counts an amount that a fee will
  immediately remove.
- **Root cause:** the solvency invariant is evaluated against a position that
  doesn't include a cost the same operation imposes; fee application and the health
  check are ordered/computed inconsistently.
- **How it's fixed:** include the fee in the amounts fed to the health check (check
  the post-fee debt/collateral), or take the fee before the check so it operates on
  the real resulting position.
- **Languages:** solidity
- **Typical severity:** medium (user self-bricks into instant liquidation / bad debt)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf

### Interest/reward index not accrued before a balance-changing op (and accrual lives only in a bypassable wrapper)
- **Look for:** a protocol with a global accrual step (`updateState()`,
  `publican.collect()`, `drip()`, `updateRewards()`) that **must** run before any
  action that changes the balance the rate is computed on (deposit, withdraw,
  borrow, repay). Two failure shapes: (a) some entry points call the accrual and
  others **forget** — e.g. `depositEth`/`redeemEth` skip the `beforeDeposit` hook
  that regular `deposit`/`redeem` run, so interest is settled against the wrong
  utilization and borrowers over/under-pay; (b) the accrual is only performed in a
  **periphery/wrapper** contract (`VaultActions`) while the **core**
  (`codex.modifyCollateralAndDebt`) is directly callable — a user who calls the
  core directly repays/borrows at a **stale** rate and skips owed interest.
- **Root cause:** the "accrue to now before mutating" invariant is enforced per
  call-path (or only in a convenience wrapper) instead of inside the core
  state-changing function itself.
- **How it's fixed:** call the accrual at the top of the **core** mutating function
  (so every path — direct or wrapped — settles first), not just in wrappers or
  some siblings; a keeper that periodically pokes accrual is a mitigation, not a
  substitute. Add a test asserting the index advances on every balance-changing entry.
- **Languages:** solidity
- **Typical severity:** medium–high (mis-accrued interest/rewards; value leaks to the
  party who times the stale window)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf

### Fee/rate applied with a different scale than it's defined in (BPS vs ‰, wrong offset)
- **Look for:** a fee or rate stored in one unit but divided by the wrong
  denominator where it's used: a `VAULT_FEE`/`feeBps` set in **basis points**
  (x / 10_000) but applied as `amount * fee / 1000` (10× too large), a percentage
  used as if it were a WAD, or a packed/`immutable` fee read with the **wrong byte
  offset** so it comes back ~1e16× off. The result is silent over- or
  under-charging — a strategist/fee-recipient quietly earns 10× (or can drain the
  whole vault) while the code "looks" like a normal fee calc.
- **Root cause:** the scale a value is defined in (BPS, ‰, WAD, packed slot) isn't
  matched by the divisor/offset at the use site; same-type integers hide the error.
- **How it's fixed:** use one named constant for the denominator (`BPS = 10_000`)
  everywhere and divide by it consistently; unit-test the fee against a known
  input/expected output; verify packed-storage offsets against the layout. Pair
  with the decimals-assumption cue in `oracle-manipulation.md`.
- **Languages:** both
- **Typical severity:** high (systematic value leak to the fee recipient / drain)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.28%20-%20Final%20-%20Rage%20Trade%20Audit%20Report.pdf (MAX_BPS = 1000 instead of 10_000 makes slippage 10× worse than intended)

### Unstake/burn recomputes user value from current parameters instead of storing the original
- **Look for:** a stake/lock/deposit that computes a derived amount from live
  parameters (`multiplier`, `baseVotes`, `rate`, `rewardPerShare`) and adds it
  to a user balance — but the **unstake/unlock/withdraw** path re-runs the same
  formula with the **current** (possibly changed) parameters and subtracts the
  newly computed value. If an admin updates the multiplier between stake and
  unstake, the subtracted amount ≠ the added amount: an increase causes
  arithmetic underflow (uint revert → user's tokens permanently locked); a
  decrease silently leaves the user with inflated balance. Tell: `stake` calls
  `getTokenVotingPower(id)` (which reads `monsterMultiplier`) and adds to
  `votesFromOwnedTokens`; `unstake` also calls `getTokenVotingPower(id)` using
  the same live multiplier rather than a stored snapshot.
- **Root cause:** the "delta applied at stake time" and "delta removed at
  unstake time" must be the same value, but the system recomputes instead of
  storing; any intervening parameter change breaks the symmetry.
- **How it's fixed:** store the original computed delta in a per-user/per-token
  mapping at stake time (`stakedVotingPower[tokenId] = computedAmount`), and use
  that stored value — not a fresh computation — when reversing the operation. This
  makes stake/unstake symmetric regardless of parameter changes.
- **Languages:** solidity
- **Typical severity:** high (token/NFT permanently locked on underflow; or
  inflated votes/shares when parameter decreases)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.01%20-%20Final%20-%20Frankendao%20Audit%20Report.pdf

### Balance-delta measurement uses wrong asset representation for external-call receive-amount
- **Look for:** a "balance before / after" pattern that measures received amount
  from an external call (aggregator swap, yield-harvester, liquidation) using a
  *different* token than what the external call actually returns. Classic case:
  `toTokenBalanceBefore = IERC20(WETH).balanceOf(this)` → external call →
  `received = IERC20(WETH).balanceOf(this) - toTokenBalanceBefore`, but the
  external call (a DEX aggregator, Paraswap, etc.) **unwraps WETH to native ETH**
  as its final step — WETH delta is 0 even though ETH was received. Variants:
  measuring aToken balance for a path that returns the underlying, measuring
  vault-share balance for a path that redeems to base asset, measuring one side
  of a wrapper pair when the other was used.
- **Root cause:** the protocol assumes the external call will settle in one
  specific form (WETH), but the integratee's internal path wraps/unwraps it to a
  different representation (native ETH); the measurement picks the wrong token to
  observe.
- **How it's fixed:** either (a) measure the actual representation the
  integratee returns (e.g. use `address(this).balance` for ETH settlement), or
  (b) instruct/constrain the external call to settle in the form you measure (add
  a `require(toToken != ETH_ADDRESS)` for WETH-measuring paths), or (c) measure
  *both* representations and sum them. Document which forms each aggregator
  returns and add integration tests against the real target.
- **Languages:** solidity
- **Typical severity:** high (computed receive amount = 0 → minimum-out check
  reverts, or entire swap silently yields nothing to the protocol)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20DODO%20Audit%20Report.pdf (M-3: `externalSwap` measures WETH balance delta, but Paraswap's `swapOnUniswapV2Fork` unwraps WETH to native ETH → delta 0 → `receiveAmount = 0`) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Lyra%20Audit%20Report.pdf (H-3: `hedgeDelta()` computes `collateralDelta` to pass to GMX's `decreasePosition`, but doesn't subtract the negative-PnL adjustment that GMX internally deducts from effective collateral before applying the delta → delta exceeds the adjusted collateral → `decreasePosition` reverts → hedge permanently broken)

### Async request submits asset transfer immediately but accounting variable only catches up on execution — stale-NAV window

- **Look for:** any two-phase async protocol flow (GMX PositionRouter, async
  oracle-keeper, cross-chain request) where: (1) the protocol **transfers assets
  out** of its main accounting pool immediately when the request is *submitted*, and
  (2) the **accounting variable** that represents those assets in pool valuation
  (e.g. `usedDeltaLiquidity`, `pendingCollateral`) is only updated when the async
  request *executes* — a potentially later transaction. During the gap the pool's NAV
  calculation sees a reduced on-chain balance (the assets are gone) but the accounting
  variable hasn't caught up → NAV appears deflated. An attacker times a large LP
  deposit into this window to mint shares at the artificial low price. Inverse: if the
  accounting variable is credited on submission but the asset isn't sent until
  execution, NAV is transiently inflated.
- **Root cause:** the pool's NAV invariant (`assets = balance + accountingVar`) holds
  in steady state but is broken transiently: the balance side is updated immediately on
  submission while the accounting side lags to the execution callback.
- **How it's fixed:** on **submission** immediately add the pending outflow to the
  accounting variable (e.g. query the pending router amount via
  `_getPendingIncreaseCollateralDelta()` and include it in `usedDeltaLiquidity`); on
  **execution** confirm/settle the final amount. Never let an asset transfer leave a
  window where the pool's computed NAV is lower than its economic value.
- **Languages:** solidity
- **Typical severity:** medium (share price manipulation via timed deposit; loss
  proportional to attack capital and pending-order time window)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Lyra%20Audit%20Report.pdf (H-2: `updateCollateral()` sends quote to GMX hedger immediately but only updates `usedDeltaLiquidity` when the GMX order executes → NAV appears deflated during the pending window → attacker deposits into LP to mint extra shares at suppressed token price)

### State-unwinding path (cancel / close) forgets to return escrowed funds
- **Look for:** an escrow/auction/offer flow where the "happy path" refunds or
  forwards held funds but an **alternate exit** doesn't. Canonical: `createBid`
  refunds the previous highest bidder, but `cancelAuction` / `closeAuction` has
  **no** refund of the current highest bid — the borrower cancels (repaying debt)
  and the standing bidder's escrowed funds are stranded or seized. Same shape:
  cancel/withdraw paths that skip returning a deposit, release collateral without
  clearing liens, or pay out a fee that was already collected on the bid. Often
  front-runnable: let bids accrue, then cancel just before a winning bid settles.
- **Root cause:** funds escrowed on one path, but the symmetric return is only
  wired into *some* of the ways that path can terminate; the cancel/close branch
  was added without unwinding the held balance.
- **How it's fixed:** every terminal branch that ends the escrow must run the same
  refund/settlement (factor it into one `_handleOutgoingPayment`/unwind helper
  called by bid-replace **and** cancel **and** close); add tests asserting the
  standing bidder's balance is made whole on every exit.
- **Languages:** solidity
- **Typical severity:** high (bidder/depositor funds lost or collateral locked)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.27%20-%20Final%20-%20Nouns%20DAO%20Audit%20Report.pdf (M-7: `rescueERC20` forbids stream token entirely — over-funded stream can only be drained by canceling; fix: allow rescue of surplus above `remainingBalance`)
