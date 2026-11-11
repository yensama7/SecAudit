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
