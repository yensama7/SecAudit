# Workflow: full source coverage

The audit is not complete while any in-scope file is unexamined. The ledger
(`coverage.json`) is the source of truth, not your memory.

## Ledger row (one per in-scope file)
```json
{
  "path": "src/Vault.sol",
  "language": "solidity",
  "discovered": true,
  "examined": false,
  "cross_referenced": false,
  "excluded": false,
  "exclusion_reason": null,
  "notes": "",
  "unresolved_questions": []
}
```

## Procedure
1. Initialize the ledger from `source-inventory.json` (all in-scope files,
   `examined: false`).
2. **Pass 1 (breadth)** — read every file once. Set `examined: true`, jot the
   contract/module purpose and any suspicions in `notes`. Cheap, builds the map.
3. **Pass 2 (depth)** — revisit money/privilege-heavy files and every suspicion.
   Follow calls across files; set `cross_referenced: true` when you've traced a
   file's external interactions. Record open questions in
   `unresolved_questions`.
4. For large repos: analyze in dependency order, summarize big files rather than
   re-reading them whole, and use grep/AST to find callers/callees instead of
   loading everything into context. Complete *recorded* examination is the goal,
   not one giant prompt.
5. If a file genuinely can't be examined, set `excluded: true` +
   `exclusion_reason`. Never leave it silently `examined: false`.
6. Run `scripts/validate_coverage.py coverage.json`. It fails if any in-scope
   file is neither examined nor excluded-with-reason. Fix before handoff.

## Done means
Every row is `examined: true` OR `excluded: true` with a reason. Any file still
`examined: false` and not excluded = audit incomplete; the final report must say
so.
