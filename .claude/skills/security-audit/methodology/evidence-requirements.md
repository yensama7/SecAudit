# Evidence requirements

A finding without current-repo evidence is a guess. Every finding must carry:

1. **Location** — `path:startLine-endLine`, real lines in THIS repo. Quote the
   offending code (the few lines that are actually wrong), not a whole function.
2. **Root cause** — the specific wrong assumption or missing check, in one or two
   sentences. "Reentrancy" is a category, not a root cause. The root cause is
   "`withdraw()` sends ETH via `.call` on line 42 before zeroing `balances[msg.sender]`
   on line 45, and has no reentrancy guard."
3. **Reachability / preconditions** — who calls it, from what state, with what
   permissions. Name the entry point. If a precondition is unverified, say which.
4. **Impact** — the concrete consequence tied to this protocol (which funds,
   which invariant, how much), not a generic sentence.
5. **A concrete trigger** — the sequence of calls/state that exploits it. If you
   can't write the sequence, your confidence is at most Medium and you say why.
6. **Remediation** — the specific fix (add guard, reorder to CEI, use
   `safeTransfer`, check return value), not "validate input".

## Trace, don't pattern-match

The failure mode of an AI auditor is reporting a pattern that looks like a bug
but is actually guarded elsewhere. Before writing a finding, you must have:

- Read the function **and** its modifiers.
- Followed each external call to see what's reachable.
- Checked callers to confirm the entry is actually exposed (not internal-only,
  not already-guarded by the only caller).
- Confirmed the "missing" check is really missing, not in a modifier, a base
  contract, or a `require` you skimmed past.

If you haven't done the trace, you don't have evidence — you have a hunch. Hunches
go in "unresolved questions", not in findings.

## Quoting

Prefer: ```solidity\n// Vault.sol:40-45\n(bool ok,) = msg.sender.call{value: amt}("");\nrequire(ok);\nbalances[msg.sender] -= amt;  // state update AFTER external call\n```
Over: "The withdraw function has a reentrancy vulnerability."
