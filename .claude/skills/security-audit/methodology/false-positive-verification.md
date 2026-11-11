# False-positive verification gauntlet

Run EVERY candidate finding through this before it earns a slot. Competitive
audits punish false positives — a wrong High wastes judges' time and tanks
credibility. When in doubt, downgrade confidence, don't delete; but a candidate
that fails any gate below is not a finding.

## The gates

1. **Is the check actually missing?** Re-read the function, its modifiers, the
   constructor/initializer, and any base contract. Grep the repo for the
   variable/role you think is unprotected. The guard is often one layer up.

2. **Is the entry point reachable by an attacker?** `internal`/`private` with no
   external caller = not reachable. `onlyOwner` on the only path, with owner
   trusted per the repo's model = not an attacker path. Confirm msg.sender can
   reach the sink with attacker-controlled data.

3. **Is the dangerous input attacker-controlled?** An external call to a
   protocol-deployed, immutable, trusted contract is not "arbitrary external
   call". A price from a hardcoded Chainlink feed is not "oracle manipulation"
   unless the feed itself is the issue.

4. **Does an existing mechanism already prevent it?** `nonReentrant`, CEI
   ordering, SafeERC20, Solidity 0.8 overflow checks, `onlyInitializing`,
   pause, access list — check before claiming the class of bug.

5. **Does the precondition actually occur?** "If admin sets fee > 100%" — can
   they? Is there a cap? "If token is fee-on-transfer" — are such tokens in
   scope? Read the README / scope / token assumptions.

6. **Is impact real for THIS protocol?** Rounding that always favors the
   protocol by 1 wei is Low/Info, not High. A revert in a view function is not
   a DoS of funds. Grief that costs the attacker more than the victim loses is
   usually not worth a High.

7. **Is it in scope?** Vendor/`node_modules`/`lib/openzeppelin`/generated code
   is typically out of scope. Known-good library code is not your finding unless
   it's used wrong by the in-scope code.

## Outcome

- Passes all gates with a full trace -> finding, confidence High.
- Passes but one precondition unverified -> finding, confidence Medium, note the
  gap.
- Fails a gate -> not a finding. If still nagging, log it in
  "unresolved questions", not in the findings list.
