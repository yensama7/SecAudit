# State transition / invariant — what to look for

### Swallowed failure (try/catch) while partial state already advanced → lockout
- **Look for:** a `try external.call() { } catch { emit Error(...) }` that does
  **not** revert on failure, where some state was already mutated before the call
  (e.g. each signer's `lastSignedRound` is bumped, but the feed's
  `latestAggregatorRoundId` only advances inside the call that just failed). The
  two pieces of state now disagree, and a later guard (`require(lastSignedRound <
  roundId)`) permanently rejects the very participants who tried — they can't
  re-submit the same round.
- **Root cause:** non-atomic update — a best-effort `try/catch` lets the tx
  succeed while leaving half-applied state; the failure is logged, not rolled back.
- **How it's fixed:** make the operation atomic — revert on the failure (or only
  advance the per-participant state inside the same success path that advances the
  shared state), so either all of it happens or none does.
- **Languages:** solidity
- **Typical severity:** medium (liveness / lockout; occasionally fund-locking)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.06%20-%20Final%20-%20Flux%20Audit%20Report.pdf

### Cached/derived value not recomputed in every mutator of its inputs → stale
- **Look for:** a stored variable derived from other state (`unit =
  maxDuration / (curve.length - 1)`, a cached `pricePerShare`, `totalWeight`, a
  precomputed index/divisor) that is recalculated in the constructor and in
  **some** setters (`init`, `setCurve`) but **not** in every function that can
  change its inputs (e.g. `setCurvePoint` pushes/pops the curve array yet never
  updates `unit`). After the omitted mutator runs, the derived value is stale and
  every consumer (here `getMultiplier`) computes wrong results — over- or
  under-paying users. Tell: a formula duplicated in two setters but missing from a
  third that touches the same backing array/length.
- **Root cause:** a derived invariant is maintained by hand at each write site
  instead of centrally, and one write site was missed.
- **How it's fixed:** recompute the derived value in **every** mutator of its
  inputs (or compute it on read from live state so it can't go stale); centralize
  the update in one internal helper that all setters call.
- **Languages:** both
- **Typical severity:** medium–high (mispriced shares/multipliers; monetary impact)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf

### "Improve-only" operation recomputes from scratch and can leave the user worse off
- **Look for:** an `extend` / `increase` / `topUp` / `upgrade` that is *intended*
  only to strengthen a position but recomputes the new value from current inputs
  and blindly writes it — e.g. `extendLock` sets a new multiplier/`shareAmount`
  from `end - block.timestamp + increase`, which can be **less** than the
  already-granted amount (extending a half-elapsed long lock by the minimum burns
  shares / cuts rewards). The user calls it expecting a gain and silently loses.
  Tell: the function `_mint`s the positive delta but handles the negative-delta
  branch by burning (or just overwrites) instead of rejecting it.
- **Root cause:** no monotonicity guard — the operation doesn't enforce
  `new >= old` for the quantity it's supposed to only increase.
- **How it's fixed:** `require` the recomputed value is ≥ the existing one (revert
  otherwise), or defer the change until it's actually beneficial (a "deferred
  lock" applied at expiry); never silently reduce a position in an increase-only
  path.
- **Languages:** both
- **Typical severity:** medium–high (unexpected loss of user value/rewards)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf

### Validate-on-raw-then-transform: check passes the raw input but the transform rounds it into the invalid range
- **Look for:** a function that **validates** a user-supplied value and then
  **normalizes/rounds** it — in that order. The check runs on the pre-transform
  value and the action runs on the post-transform value. If the normalization can
  move a "just-valid" input into an invalid range, the check is effectively
  bypassed. Classic shape: a time/expiry check (`if (expiry < block.timestamp)
  revert`) followed by a rounding step (`expiry = roundDown(expiry, 1 days)`)
  that can round a timestamp from 1 second in the future down to a timestamp from
  hours ago — the check saw "future" but the stored/used value is "past." Same
  class: a `minPrice` check on a raw amount before a fee is applied, or a
  collateral sufficiency check before an interest-accrual step.
- **Root cause:** the validation and the data transformation use different
  representations of the same value; the invariant must hold for the **consumed
  form**, not the input form.
- **How it's fixed:** **normalize first, then validate** — perform the same
  rounding/transformation the downstream will use, then check the result against
  the invariant. The validation must operate on the same value that will be
  stored/acted on.
- **Languages:** solidity
- **Typical severity:** high (invariant guaranteed by a check that doesn't apply
  to what's actually used — e.g. expired bond tokens minted as if unexpired)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.29%20-%20Final%20-%20Bond%20Protocol%20Audit%20Report.pdf

### Dynamic array reordered on removal, but elements referenced by stored index
- **Look for:** a dynamic array whose removal path **reorders** it — `delete` +
  shorten, or swap-last-into-gap + `pop()` (`arr[i] = arr[arr.length-1]; arr.pop()`)
  — while other code refers to entries by a **position/index** captured earlier (a
  stored `lienPosition`, an index passed into a loop or a payment call, a cached
  `i`). After any removal the indices shift, so a later reference points at the
  **wrong** element or reverts out-of-bounds. Two concrete harms: (a) batch
  payment/liquidation loops over `[0..len)` revert once one entry is paid off and
  the array shrinks; (b) an attacker who can trigger a removal (repay/buy out a
  senior position) **front-runs** a victim's indexed action to shift the array so
  the victim's payment lands on the attacker's entry instead. Classic tell: a loop
  that both pays an element and deletes it, plus a sibling deletion that
  swap-and-pops.
- **Root cause:** identity is tracked by array position, but position isn't stable
  under reordering; no stable key (id) ties a reference to the intended element.
- **How it's fixed:** reference entries by a **stable id** (a mapping keyed by a
  unique lienId/orderId), not by array index; if you must use indices, iterate a
  snapshot / iterate backwards and don't let external calls reorder mid-loop;
  validate the element at an index still matches the expected id before acting.
- **Languages:** both
- **Typical severity:** high (DoS of payments/liquidation → collateral locked; or
  forced mispayment to an attacker)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf
