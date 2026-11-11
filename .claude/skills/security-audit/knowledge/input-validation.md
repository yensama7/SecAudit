# Input validation — what to look for

### Admin/config setters missing zero-address and sanity/threshold checks
- **Look for:** external/owner setters that assign address params (collateral,
  incentivizer, beacon, treasury, oracle, pauser) or numeric params (fees, min
  collateral, ratios) with no `require(addr != address(0))` and no
  min/max/threshold bounds. Constructors wiring addresses are equally prone.
- **Root cause:** trusting the caller to pass sane values; a zero address bricks
  the path (reverts, possibly forcing redeploy), an out-of-range number can brick
  or destabilize the protocol (e.g. 100% fee, min-collateral set absurdly high).
  Also check **structural invariants on array/config params** — e.g. a multiplier
  `curve[]` the code assumes is monotonic increasing (`curve[n+1]-curve[n]`
  underflows and DoSes deposits if a later point is set lower), or a
  configuration where two fields must be consistent (an `escrowPortion > 0` paired
  with `escrowPool == address(0)` silently **strands** the escrowed rewards in the
  contract with no recovery path, instead of reverting).
- **How it's fixed:** `require(addr != address(0))` on every address setter;
  explicit range/threshold checks on numeric params; validate array ordering/length
  invariants at every write site; reject inconsistent config combinations (or make
  the dependent path handle `address(0)` by paying the user directly rather than
  escrowing to nowhere). Pair with the timelock + bounds in `access-control.md` for
  privileged knobs.
- **Languages:** solidity
- **Typical severity:** low–medium (robustness; escalates to fund-freeze / deposit DoS
  when a bad value bricks or strands funds)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.02%20-%20Preliminary%20-%20Perennial%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf (non-monotonic curve underflow; escrowPortion>0 with escrowPool==address(0) freezes rewards)

### Zero-default id/sentinel passes a validity check against an uninitialized struct
- **Look for:** struct lookups validated by `require(items[id].id == id)` (or
  similar self-consistency check) where ids are issued from a counter that starts
  at **1**. For `id == 0`, an unset mapping entry returns a zero-filled struct
  whose `.id` is also `0`, so the check passes and an **uninitialized** struct is
  treated as valid. Watch every function that accepts such an id (trade composers,
  admin setters like `setStrikeSkew`) — the owner can even poke id 0 by accident.
- **Root cause:** `0` is simultaneously the "empty mapping" value and a
  structurally valid-looking id; the counter's 1-based start leaves a gap the
  check doesn't close.
- **How it's fixed:** start the id counter at 0 so the first real id can't collide
  with the empty default, or explicitly `require(id != 0)` in every function that
  consumes the id; add a dedicated "exists" flag rather than inferring existence
  from a field value.
- **Languages:** solidity
- **Typical severity:** low–medium (depends on what an uninitialized struct enables)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.27%20-%20Final%20-%20Lyra%20Audit%20Report.pdf

### Caller-supplied value that the contract could derive is accepted unverified
- **Look for:** a function parameter that represents a quantity the contract
  already has the inputs to compute itself (an `_awardAmount`, `_totalShares`,
  `_price`, `_index`, `_expectedBalance`), passed in by the caller and then used
  (or forwarded to a module/hook) **without a check** that it equals the derived
  value. Tell: a comment or sibling function shows the correct derivation (e.g.
  `cliffAmount + periods * perPeriod`) but this path trusts the argument. Also:
  view/helper functions (`getClaimableAmount`) that return a value without
  verifying the subject actually exists / is in the Merkle set, which integrators
  may then trust.
- **Root cause:** trusting the caller for a value that should be authoritative
  from on-chain state; the parameter is a redundant, attacker-controllable input.
  Related: an ownership/state guard that recomputes an id from **caller-supplied**
  inputs and compares it to stored state — e.g. `unbond` checks
  `proposals[rateId] == computeProposalId(rateId, msg.sender, value, nonce)` where
  `value`/`nonce` come from the caller, so the attacker just passes inputs that make
  the equality true or false at will and bypasses the "is this your active
  proposal?" check. Key such guards on **stored** state (a `proposer[rateId]`
  mapping), not on recomputation from arguments.
- **How it's fixed:** drop the parameter and compute the value in-contract, or
  `require` it equals the derived value before use; in view helpers, verify
  membership/existence before returning a non-zero result; base authorization on
  stored state rather than caller-reconstructed ids.
- **Languages:** solidity
- **Typical severity:** low–high (safe if the current consumer ignores it, but
  fatal — fund theft — if any module/integrator trusts it)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.08.24%20-%20Final%20-%20LiquiFi%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf (unbond guard keyed on caller-supplied value/nonce)

### Inverted condition when migrating `require(cond)` to `if (!cond) revert Error()`
- **Look for:** a refactor that replaced `require` statements with custom-error
  `if (…) revert …` checks (common for gas/readability), where the condition was
  **not** correctly negated. `require(x.length > 0)` must become
  `if (x.length == 0) revert …` — a mistranslation to `if (x.length != 0) revert …`
  inverts the guard, so it now rejects the **valid** case and accepts the invalid
  one, silently breaking functionality (or disabling a safety check). Hot spots:
  ported library code (RLP/Merkle verifiers, math libs), any diff that swaps
  `require` for `revert` in bulk. Same family of boolean-logic slips: using `&&`
  where the spec says "**either** condition" (a refinance check that should accept
  "rate dropped **OR** duration grew" but `require`s both, rejecting valid cases),
  and a **comparison in the wrong direction** (computing `minNewRate = rate -
  delta` then checking `newRate >= minNewRate`, which accepts rate *increases* —
  the opposite of "rate decreased"). Cross-check every multi-condition validity
  check and every `>=`/`<=` against the written spec.
- **Root cause:** `require(cond)` reverts when `cond` is false; the `if`-revert form
  must test `!cond`, and a hand-negation error flips the logic. Compiles cleanly.
- **How it's fixed:** mechanically negate (`require(c)` → `if (!c) revert`); add
  tests for both the passing and failing case of each migrated check; review
  such refactors condition-by-condition rather than trusting the bulk edit.
- **Languages:** solidity
- **Typical severity:** low–high (a disabled/flipped check; impact = what it guarded)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (isValidRefinance used AND instead of OR, and checked rate increased instead of decreased)

### Guard statement with no effect — a check is written but never enforced
- **Look for:** a validation whose consequence was dropped so the statement is a
  silent no-op. Canonical shape: `if (!isContract(target)) Errors.AddressNotContract;`
  — a bare reference to an error/constant with **no `revert`**, which compiles,
  does nothing, and lets the "only contracts" check pass for everything (then a
  `delegatecall` to an EOA returns `success` because empty code = STOP). Same
  smell: a `require`/assert computed into a local that's never checked, a boolean
  result ignored, a modifier defined but not applied, `x == y;` instead of
  `require(x == y)`. These slip past review because the line *looks* like a guard.
- **Root cause:** the enforcement half of a check (the `revert`/`require`) is
  missing, so the condition is evaluated and discarded.
- **How it's fixed:** make the check actually revert (`if (!cond) revert …;` /
  `require(cond)`); enable a compiler/linter warning for unused expression
  statements and return values; add a test that feeds the bad input and asserts a
  revert.
- **Languages:** solidity
- **Typical severity:** low–high (a disabled safety check; impact = whatever the
  check was protecting)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf

### Hardcoded 4-byte selector encodes version-specific calldata / default args
- **Look for:** an integration allowlist that stores raw function selectors
  (`bytes4 constant WITHDRAW = 0x2e1a7d4d;`) or builds calldata for an external
  protocol, where the selector/ABI is tied to a **specific** deployment or
  overload. Two failure modes: (a) the target contract has **multiple versions**
  (e.g. UniswapV3 Router vs Router2 dropped a `deadline` arg) so the stored
  selectors don't match the deployed router → every call reverts (feature DoS);
  (b) a short overload selector silently encodes a **default parameter** that
  matters — `withdraw(uint256)` on a Yearn vault means `maxLoss = 1 bps`, so a
  withdrawal reverts whenever realized loss exceeds that, locking funds.
- **Root cause:** selectors/calldata hardcode an assumption about which contract
  version and which overload is deployed and what its omitted args default to;
  nothing re-validates it against the actual target.
- **How it's fixed:** pin the exact deployed contract/version the selectors were
  derived from (document the address), or support both overloads; prefer the
  explicit overload that takes the safety-relevant parameter (e.g. `maxLoss`)
  rather than relying on a default; add an integration test against the real
  target address.
- **Languages:** solidity
- **Typical severity:** low–medium (integration DoS / funds temporarily locked)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf
