---
name: security-audit
description: Audit a smart-contract / Rust repository for vulnerabilities, then automatically cross-reference findings against a knowledge base of historical competitive-audit findings. Use when the user opens a repo and asks for a security audit, a vulnerability review, a competitive-audit pass, or says "audit this", "find bugs", "review for vulnerabilities" on Solidity (.sol) or Rust (.rs) code.
---

# Security Audit — parent orchestrator

You run a **two-stage** audit. Both stages run from this one invocation. You do
NOT stop after stage 1 and wait for the user — stage 2 is automatic and
mandatory once the handoff validates.

## The non-negotiable sequence

```
Stage 1  Security Auditor   -> writes .security-audit/auditor-findings.json
            |
            v   (validate_handoff.py must pass)
Stage 2  Audit Intelligence -> writes .security-audit/intelligence-results.json
            |
            v
Final report               -> .security-audit/final-report.md
```

Do not rely on memory to switch stages. After stage 1, you MUST run the
validator script; if it exits 0, you MUST run stage 2. If it exits non-zero,
STOP and report the failure — do not fake a handoff.

---

## STAGE 0 — Setup (always first)

1. Confirm the repo root (the directory the user opened, unless they point
   elsewhere). Record the git commit: `git -C <root> rev-parse HEAD` (ok if not
   a git repo — record "no-vcs").
2. Create the output dir: `.security-audit/` at the repo root.
3. Run discovery:
   `python <SKILL_DIR>/../../../scripts/discover_sources.py <root> --out .security-audit/source-inventory.json`
   This classifies every `.sol`/`.rs` file as in-scope vs vendor/generated/test.
4. Read `source-inventory.json`. This is your file list. Initialize the coverage
   ledger `.security-audit/coverage.json` with one row per in-scope file, all
   marked `examined: false`.

Read `workflows/repository-discovery.md` for how to classify scope and find
entry points / trust boundaries.

## STAGE 1 — Security Auditor

Goal: examine **every** in-scope file and produce substantiated findings.

1. Read the methodology and distilled knowledge you need:
   - **Distilled knowledge (what to look for + how such bugs are fixed):**
     `knowledge/INDEX.md`, then the relevant `knowledge/<category>.md` files for
     the categories in scope (reentrancy, oracle-manipulation, access-control,
     …). These are lessons extracted from historical Sherlock/Cyfrin audits — use
     each pattern's **Look for** cue to guide where you search and its **How it's
     fixed** to judge whether the current code already applies the known remedy.
   - Severity & evidence rules: `methodology/severity-model.md`, `methodology/evidence-requirements.md`
   - Optional, if present: `languages/<lang>/taxonomy.md` / `audit-checklist.md`.
2. Follow `workflows/full-source-coverage.md`: walk files in dependency order,
   update `coverage.json` as you examine each. **No in-scope file may stay
   `examined: false`.** If you truly cannot examine one, set
   `excluded: true` + a reason — never silently skip.
3. Hunt vulnerabilities per `workflows/vulnerability-hunting.md`. For each
   candidate, run the false-positive gauntlet in
   `methodology/false-positive-verification.md` BEFORE writing it down.
4. Write findings to `.security-audit/auditor-findings.json` conforming to
   `templates/findings.schema.json`. Return up to 20 — the strongest distinct
   ones. **Do not invent findings to reach 20.**
5. Validate coverage:
   `python <...>/scripts/validate_coverage.py .security-audit/coverage.json`
6. Validate the handoff:
   `python <...>/scripts/validate_handoff.py .security-audit/auditor-findings.json`
   - exit 0 -> proceed to stage 2.
   - exit non-zero -> fix the findings file or STOP and report. Never proceed on
     an invalid handoff.

## STAGE 2 — Audit Intelligence (automatic)

Cross-check each finding against the **distilled knowledge library**
(`knowledge/<category>.md`). Read `workflows/intelligence-handoff.md`, then for
EACH finding in the validated handoff:

1. Open the `knowledge/<category>.md` matching the finding's category. Find the
   pattern(s) whose **Look for** cue matches this finding's root cause/shape.
2. Use the pattern's **How it's fixed** to check the ACTUAL current code: does it
   already apply that remedy, or is it genuinely missing? Read the real
   functions, callers, callees, and state — do not conclude from the cue alone.
3. Also sweep the library for patterns in this finding's category that you did
   NOT raise, and confirm whether the code is actually safe against each — this
   catches misses, not just confirms hits.
4. Record a verdict per `workflows/finding-verification.md`: `confirmed`,
   `similar_unestablished`, `rejected`, `inconclusive`, or `no_match`.
5. Write all of this to `.security-audit/intelligence-results.json`.

Optional (legacy raw-findings corpus, only if populated): the MCP tool
`search_audit_findings` / `python intelligence-engine/retrieve.py "<query>"
--lang <l> --category <c>` can surface individual historical findings. The
distilled library is the primary source; use retrieval only to supplement.

**Similarity is never confirmation.** A matching pattern guides investigation;
it does not establish a vulnerability. Do not raise severity because a similar
historical finding was severe.

## STAGE 3 — Final report

`python <...>/scripts/build_final_report.py --dir .security-audit`
assembles `final-report.md` from the artifacts. Then read it, write the
executive summary and per-finding verification judgements into it, and present
the top findings to the user in chat.

If coverage was incomplete, the report MUST say so up top. Never present an
incomplete audit as complete.

---

## Ground rules (apply in every stage)

- **Evidence before judgement.** Every finding cites real file:line in THIS repo.
- **Complete, recorded coverage.** The ledger is the source of truth.
- **Confidence is separate from severity.** A critical-impact bug you're 50% sure
  is reachable is High severity / Low confidence — say both.
- **The absence of a historical match does not mean the code is safe.**
