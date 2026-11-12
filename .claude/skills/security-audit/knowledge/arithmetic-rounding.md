# Arithmetic / rounding / overflow — what to look for

### Unchecked `mul`/`div` in a math library under Solidity < 0.8
- **Look for:** a math/vector library (`VecMath`, `FixedPoint`, custom WAD/RAY
  helpers) declaring `pragma solidity 0.7.x` (or lower) and using raw `*` / `/`
  with no SafeMath. Pre-0.8 arithmetic does not revert on overflow/underflow.
  Especially risky for reusable libs that may be forked or wired into new call
  sites later, even if every *current* usage happens to be in-range.
- **Root cause:** reliance on callers staying within bounds rather than the
  operation itself being checked; the guarantee lives in usage, not in the code.
- **How it's fixed:** use SafeMath (pre-0.8) or compile with Solidity ≥ 0.8
  (checked arithmetic); where intentional wrapping is needed, isolate it in an
  explicit `unchecked` block with a comment justifying bounds.
- **Languages:** solidity
- **Typical severity:** low–critical (here low — no current usage overflowed —
  but the impact if it did would be large; judge by reachable inputs)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.02.09%20-%20Final%20-%20Tempus%20Audit%20Report.pdf

### Rounding direction favors the user → pool left short → last withdrawer reverts
- **Look for:** pro-rata share/claim math using round-**up** helpers (`wmul`/`wdiv`
  that round up, `ceilDiv`) when computing how much each user receives from a
  shared pool. Each payout is a hair larger than the exact share, so the pool runs
  a cumulative dust deficit and the **last** user to claim/withdraw reverts for
  lack of balance — their funds are stuck. (Mirror image: rounding that favors the
  *protocol* on deposits but the *user* on withdrawals lets value be skimmed.)
- **Root cause:** rounding direction not chosen to protect the pool invariant
  (Σ payouts ≤ pool balance); round-up on outflows breaks it.
- **How it's fixed:** round **down** on amounts leaving the pool (round up only in
  the protocol's favor); or give the last claimant a "withdraw remaining balance"
  path so dust can't lock them out. Audit every `mul`/`div` for who the rounding
  favors.
- **Languages:** solidity
- **Typical severity:** low–medium (stuck dust / last-user lockout; or slow skim)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.07.05%20-%20Final%20-%20Opyn%20Squeeth%20Crab%20V2%20Audit%20Report.pdf

### Unsafe downcast (uint256 → uintN) silently truncates → loss / wrong value
- **Look for:** explicit narrowing casts like `uint128(amount)`, `uint64(ts)`,
  `uint96(x)` applied to a value that can exceed the target width — an amount
  accumulated into a `uint128` slot, an ERC721 `tokenId` (full uint256 range)
  forced into a `uint128` parameter, a timestamp/price packed into a small field.
  Solidity's checked arithmetic (0.8+) does **not** catch truncating casts, so the
  high bits are dropped silently (`uint128(2**128)` → 0), corrupting accounting or
  making a function unable to address large ids.
- **Root cause:** storage-packing / gas optimization chose a width smaller than
  the value's real range, and the cast isn't range-checked.
  making a function unable to address large ids. Watch especially for a range
  check placed **after** the cast (`uint88 x = uint88(amount); require(x <= MAX)`)
  — the truncation already happened, so the check is on the wrong value and is
  useless; a separately-used `amount`/`deltaCollateral` then diverges from the
  truncated field.
- **Root cause:** storage-packing / gas optimization chose a width smaller than
  the value's real range, and the cast isn't range-checked (or the check runs too
  late, after truncation).
- **How it's fixed:** use OpenZeppelin `SafeCast` (reverts on overflow) for every
  narrowing cast, or widen the field to `uint256`. Audit each `uintN(` cast for
  whether the source can exceed `type(uintN).max`; validate the bound **before**
  casting, not after.
- **Languages:** solidity
- **Typical severity:** low–high (silent truncation → fund loss / locked feature)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.12%20-%20Final%20-%20Harpie%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf (uint88 cast with a check that runs after the cast)

### Proportional N-way split floors each bucket → aggregate falls short of total
- **Look for:** a function that splits a total amount across N recipients/paths
  using the formula `bucket[i] = total * weight[i] / sumWeights` applied
  independently to each `i`. Because each term floors, `Σ bucket[i] ≤ total`
  with the shortfall equal to accumulated dust. If the last path is then
  called with `bucket[N-1]` (the floor value) but downstream expects the
  exact remainder, the protocol either (a) sends too little and the
  `minReturn` check reverts, or (b) leaves unaccounted dust in the contract.
  Tell: a split loop where each iteration computes `curAmount = curTotal *
  w[i] / totalW` without special-casing the last iteration.
- **Root cause:** independently flooring each proportional amount discards up
  to N-1 dust units; the aggregate is strictly less than the input total.
- **How it's fixed:** accumulate the sent amounts in a running sum; for the
  last bucket use `remainder = total - sumPrevious` instead of the floored
  formula — this guarantees `Σ = total` and needs no floating-point. Also
  round all earlier buckets consistently (down or up) to avoid systematic bias.
- **Languages:** solidity
- **Typical severity:** low–medium (small dust loss per tx; reverts if a
  strict `minReturn` is set)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20DODO%20Audit%20Report.pdf (M-2: `curAmount = curTotalAmount * weight / totalWeight` in split loop; last bucket underfunded by accumulated dust)

### Divide-before-multiply: intermediate division truncates to zero when numerator << denominator
- **Look for:** a compound expression that **divides first, then multiplies**:
  `(a * 1e18 / b) * c / 1e18` or `(a / b) * c`. When `a << b` (the numerator of
  the first division is much smaller than the denominator), the integer division
  produces 0, and the subsequent multiplication is `0 * c = 0` — the whole
  expression silently returns zero regardless of `c`. The equivalent expression
  that avoids intermediate truncation is `a * c / b`. Canonical shapes: (a)
  `amountScaled = (amount * 1e18 / totalSupply) * price / 1e18` where `amount` is
  a small individual value and `totalSupply` is large; (b) `feeAdj / decimals * qty`
  where `feeAdj` is never a full `decimals` multiple. EVM integer arithmetic
  truncates at every `/` — the order of operations is load-bearing.
- **Root cause:** mathematically correct on paper but integer-truncates to zero in
  the EVM because `a / b` rounds down to 0 when `a < b`, discarding all precision
  before the subsequent multiplication can recover it.
- **How it's fixed:** reorder to **multiply before dividing**: `a * c / b`; use a
  higher-precision intermediate type if the product might overflow (use
  `mulDiv(a, c, b)` from FullMath/PRBMath or OZ `Math.mulDiv`); add a test with
  small `a` values to catch this truncation case.
- **Languages:** solidity
- **Typical severity:** high (key quantity evaluates to zero — deposits fail,
  collateral worth nothing, auctions always revert)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.09%20-%20Final%20-%20Opyn%20Crab%20Netting%20Audit%20Report.pdf (M-1: `((a * 1e18 / b) * c) / 1e18` rounds to 0 for small `a`; fix is `(a * c) / b`) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.27%20-%20Final%20-%20Nouns%20DAO%20Audit%20Report.pdf (M-1: `_recipientBalance` uses `elapsedTime * (MULT * tokenAmount / duration) / MULT` → unnecessary div-before-mul; fix: `elapsedTime * tokenAmount / duration`)

### Round-trip unit conversion loses 1 wei → downstream exact-amount check reverts
- **Look for:** a value converted into another unit and back — e.g.
  `deltaNormalDebt = wdiv(addDebt, rate)` then later `deltaDebt = wmul(rate,
  deltaNormalDebt)` — where each `mul`/`div` rounds **down**, so the round-tripped
  amount is 1 wei (or a few) **less** than the original. If a downstream step then
  requires the exact original amount (`transferCredit(addDebt)`,
  `exitMoneta(creditor, addDebt)`, an equality/`>=` check against the pre-conversion
  figure), it reverts for a 1-wei shortfall and the whole flow (leverage, mint,
  settle) fails deterministically.
- **Root cause:** lossy fixed-point conversion combined with a consumer that
  expects the pre-conversion amount exactly; rounding direction not aligned with
  which side must be fully covered.
- **How it's fixed:** round the conversion in the direction that covers the
  requirement (`wdivUp`/`wmulUp` on the leg that must be ≥ the needed amount), or
  carry and reconcile the dust, or relax the downstream check to the actually-minted
  amount rather than the pre-conversion input.
- **Languages:** solidity
- **Typical severity:** medium (core action reverts; funds not lost but feature DoS'd)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf
