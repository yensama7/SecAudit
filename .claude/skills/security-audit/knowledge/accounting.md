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
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.27%20-%20Final%20-%20Lyra%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf (increaseLock reads depositsOf[msg.sender] instead of depositsOf[_receiver])

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
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf

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
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf
