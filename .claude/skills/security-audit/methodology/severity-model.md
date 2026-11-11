# Severity model

Severity = **impact × likelihood**, judged for THIS codebase. It is not a vibe
and not copied from a similar historical finding. Confidence is tracked
separately (see bottom).

## Impact (what happens if exploited)

- **Critical** — direct, unbounded loss of user/protocol funds, or total loss of
  protocol integrity, with no meaningful precondition the attacker can't meet.
  (Drain a vault, mint unlimited tokens, bypass all access control on fund moves.)
- **High** — loss of funds or critical invariant break, but gated by a
  precondition (specific state, a privileged-but-not-admin role, a griefable
  window) or bounded in amount.
- **Medium** — value leak, griefing, temporary DoS of a non-critical path,
  incorrect accounting that's recoverable, or fund loss needing an unlikely
  combination of conditions.
- **Low** — limited impact: minor rounding in the protocol's favor, missing
  event, unenforced best-practice, issue requiring the victim to act against
  their own interest.

## Likelihood (how plausible is the path)

Consider: Who can trigger it? What state is required? Is it one txn or a
multi-block setup? Does it need a specific victim action, a price move, a
reorg, admin mistake? **Map it to the actual contract** — is the function
reachable, is the modifier really missing, is the external call really
attacker-controlled.

## The matrix (competitive-audit convention, e.g. Sherlock/C4)

|            | High impact | Medium impact | Low impact |
|------------|-------------|---------------|------------|
| **High likelihood**   | Critical | High   | Medium |
| **Medium likelihood** | High     | Medium | Low    |
| **Low likelihood**    | Medium   | Low    | Low    |

Notes:
- "Admin can rug" with no further bug is usually **informational / centralization**,
  not High — unless the plan's trust model says admin is untrusted.
- Requires a malicious/weird ERC20 (fee-on-transfer, rebasing, reentrant
  callback, >18 decimals) only counts if such tokens are **in scope** per the repo.
- Theoretical reentrancy guarded by `nonReentrant` or CEI is NOT a finding.

## Confidence (report separately, never fold into severity)

- **High** — you traced the full path in this repo and it holds.
- **Medium** — logic looks wrong but one precondition (reachability, a token
  assumption, an external contract's behavior) is unverified.
- **Low** — suspicious, worth flagging, but you could not confirm the path.

Report both, e.g. `Severity: High / Confidence: Medium`. Do not suppress a
real-looking bug just because confidence is Medium — say so and move on.
