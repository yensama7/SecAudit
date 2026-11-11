# Workflow: intelligence handoff (stage 1 -> stage 2)

This is the automatic transition. Do not wait for the user.

## Preconditions (all must hold before stage 2)
- `auditor-findings.json` exists and `validate_handoff.py` exits 0.
- `coverage.json` validated (or audit explicitly marked incomplete).

If `validate_handoff.py` fails: STOP. Report what failed. Do not start stage 2
on an invalid artifact.

## For each finding
1. Build a query from the fingerprint: category + operation + trust boundary +
   root-cause keywords. Example: `"reentrancy external call before state update
   withdraw vault"`.
2. Retrieve historical analogues:
   - MCP: `search_audit_findings({ query, language, category, limit: 8 })`
   - or CLI: `python intelligence-engine/retrieve.py "<query>" --lang solidity
     --category reentrancy --limit 8`
3. For promising hits, `get_finding_details(id)` and `get_audit_reference(id)`
   for the original report URL / severity / provenance.
4. **Investigate against the real code**: does the current implementation share
   the historical root cause AND satisfy the historical preconditions? Read the
   actual functions — don't decide on title similarity.
5. Record per finding in `intelligence-results.json`:
   ```json
   {
     "finding_id": "F-01",
     "matches": [
       { "source": "sherlock", "report": "...", "url": "...",
         "orig_severity": "high", "title": "...",
         "similarity_note": "same external-call-before-accounting shape",
         "verdict": "confirmed",
         "reasoning": "Vault.sol:40-45 updates balance after .call, no guard;
                       identical to the historical root cause." }
     ]
   }
   ```

## Verdicts (see finding-verification.md)
`confirmed` | `similar_unestablished` | `rejected` | `inconclusive` | `no_match`.

## Rules
- Similarity != confirmation. History guides; the code decides.
- Never raise a finding's severity because a historical match was severe.
- Preserve every source URL / report id for the final report.
- No historical match does NOT mean safe — keep the direct finding as-is.
