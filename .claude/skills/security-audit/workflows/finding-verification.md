# Workflow: finding verification (stage 2 verdicts)

When comparing a historical finding to the current code, pick ONE verdict and
justify it with current-code evidence.

| Verdict | Meaning | Required evidence |
|---|---|---|
| `confirmed` | Current code exhibits the same underlying weakness and it's reachable. | file:line here + why the historical root cause + preconditions hold now. |
| `similar_unestablished` | Same pattern/shape, but you could not establish exploitability (a precondition is unmet or unverified). | which precondition fails/unknown. |
| `rejected` | Looks similar by title but the current code does NOT have the weakness (guarded, different design, unreachable). | the mitigation/difference in this repo. |
| `inconclusive` | Not enough context to decide (needs external contract behavior, deploy config, off-chain piece). | what's missing to decide. |
| `no_match` | No relevant historical finding retrieved. | — (keep the direct finding unchanged). |

## How this affects the final report
- `confirmed` strengthens a direct finding — cite the historical precedent as
  supporting evidence, but severity still comes from THIS code's impact/likelihood.
- `similar_unestablished` / `inconclusive` -> note as an area to investigate;
  does not by itself create or raise a finding.
- `rejected` -> record it (shows the class was considered and ruled out). Useful
  signal that you checked, not a finding.
- Direct findings with `no_match` stand on their own evidence. Absence of
  history is not a safety proof.

## Hard rule
A verdict of `confirmed` requires current-repo evidence, not historical
similarity. If all you have is "the titles match", that's at most
`similar_unestablished`.
