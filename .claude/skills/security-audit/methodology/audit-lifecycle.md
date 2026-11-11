# Audit lifecycle

The order of operations for a single audit run. The orchestrator (SKILL.md)
drives this; this file is the "why" behind the sequence.

1. **Scope first, code second.** You cannot audit what you haven't inventoried.
   Build the file list and the mental model (entry points, roles, money flows,
   external dependencies, trust boundaries) before hunting bugs. A finding only
   means something relative to the trust model.

2. **Breadth then depth.** Pass 1: read every in-scope file once to build the
   map and note suspicions (cheap). Pass 2: dig into the suspicious spots and
   the high-value targets (functions that move funds, change roles, update
   critical state). Don't deep-dive file 1 for an hour before seeing file 20.

3. **Follow the money and the privilege.** Most competitive-audit bugs live where
   value moves (deposits, withdrawals, swaps, liquidations, reward math) or where
   authority is granted/checked. Prioritize those paths.

4. **Invariants.** Write down what must always be true (e.g. "sum of balances ==
   totalSupply", "collateral >= debt", "only owner can pause", "shares never
   mint for free"). Then ask: what call sequence breaks this? Many top findings
   are invariant violations, not single-line bugs.

5. **Verify before recording.** Every candidate runs the false-positive gauntlet.

6. **Coverage is a ledger, not a feeling.** Mark each file examined. The audit is
   not done while any in-scope file is unexamined.

7. **Handoff, then intelligence.** Only a validated findings artifact crosses into
   stage 2. Stage 2 enriches with history; it never invents verdicts.

## What makes a competitive-audit finding (vs a checklist tick)

Judges reward: a real, reachable path; clear impact on funds/invariants; a
concrete exploit sequence; correct severity. They reject: speculative,
unreachable, out-of-scope, already-mitigated, or "best practice" nits dressed as
Highs. Aim for the former.
