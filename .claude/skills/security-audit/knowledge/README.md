# Distilled audit knowledge

This directory is the system's **audit intelligence** — not a corpus of raw
reports, but the *lessons* extracted from historical competitive audits:
**what to look for**, **why the bug happens**, and **how it was fixed**.

It is built by the distillation workflow (`workflows/distill-knowledge.md`),
which reads real reports (Sherlock, Cyfrin, …) one at a time and merges each
distinct lesson here. Reports themselves are never stored — only these compact,
deduplicated lessons. The auditor (SKILL stage 1) reads the relevant category
file(s) while hunting, so historical experience directly instructs the review.

## Layout

```
knowledge/
  README.md              (this file — format spec)
  INDEX.md               (human-readable index of categories + counts)
  distill-state.json     (per-source cursor + convergence tracking)
  <category>.md          (one file per vulnerability category; see taxonomy below)
```

Categories match the taxonomy in `intelligence-engine/db.py` (`_CATEGORY`):
`reentrancy`, `oracle-manipulation`, `access-control`, `arithmetic-rounding`,
`share-inflation`, `signature-replay`, `initialization-upgrade`, `dos`,
`token-assumption`, `accounting`, `account-validation`, `cpi`, `mev-frontrun`,
`state-transition`, `unsafe-ffi`, `input-validation`. Add a new file only for a
genuinely new class.

## Lesson format

Each category file is a list of patterns. Keep each entry tight — this is
instruction, not a report dump. One pattern per `###` heading:

```markdown
# <Category> — what to look for

### <short, specific pattern name>
- **Look for:** the concrete code shape / smell / location that signals it
  (e.g. "external `.call` to a user-controlled address before the balance
  decrement"). This is the detection cue the auditor scans for.
- **Root cause:** why the bug exists (the wrong assumption or missing invariant).
- **How it's fixed:** the remediation that resolved it in practice
  (e.g. "checks-effects-interactions: decrement before the external call, or a
  `nonReentrant` guard").
- **Languages:** solidity | rust | both
- **Typical severity:** critical | high | medium | low (historical, not a verdict)
- **Seen in:** source report URL(s) — provenance, 1–3 examples, not exhaustive
```

## Rules

- **Distil, don't dump.** If a report's finding matches an existing pattern, add
  at most a new "Seen in" URL or sharpen the "Look for" cue — do **not** append a
  near-duplicate entry. The library converges; it does not grow per report.
- **Instruction over similarity.** The value is the detection cue + the fix, not
  "a similar finding existed." The auditor still proves every bug against the
  real code; these lessons only tell it *what to check and how such issues go*.
- **Keep provenance.** Every pattern cites at least one source URL.
- **Severity here is historical context**, never a reason to inflate a finding.
