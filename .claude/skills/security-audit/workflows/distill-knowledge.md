# Workflow: distill historical reports into knowledge

Goal: turn real competitive-audit reports into compact, instructional lessons —
**what to look for** and **how such bugs are fixed** — stored in
`knowledge/<category>.md`. Reports are read one at a time and discarded; only the
distilled, deduplicated lessons persist. This is a *convergent* pass: you stop a
source once it stops teaching you anything new.

You are driving this loop yourself (headless or interactive). Use the project's
Python helper to pull reports; use Edit to grow the library.

## Inputs / outputs

- Feed: `python intelligence-engine/report_feed.py --source <name> --index N`
  → JSON `{path, url, text, count, index, truncated}`. `--count` gives the total;
  `--list` dumps all paths. (PDFs need PyMuPDF; the helper parses them in memory.)
- Library: `.claude/skills/security-audit/knowledge/<category>.md` (format in
  `knowledge/README.md`), `knowledge/INDEX.md`, `knowledge/distill-state.json`.

## The loop (per source, e.g. sherlock then cyfrin)

1. Read `knowledge/distill-state.json`. Take this source's `cursor`,
   `no_new_streak`, and the global `convergence_threshold`. If `converged` is
   already true, skip the source.
2. `report_feed.py --source <name> --count` → `count`.
3. From `i = cursor` upward, for each report:
   a. Fetch it: `report_feed.py --source <name> --index i`. On `error`
      (fetch/parse failed), record nothing, advance, and continue.
   b. Read the text. Identify each **distinct** vulnerability it describes. For
      each, determine: category (match the taxonomy in `knowledge/README.md`),
      the concrete **detection cue** ("look for …"), the **root cause**, and the
      **how-it-was-fixed** remediation, plus language and the report's typical
      severity.
   c. For each lesson, open `knowledge/<category>.md` (create it with a
      `# <Category> — what to look for` header if missing):
      - **Already covered?** If an existing `###` pattern captures the same cue +
        fix, do NOT add a duplicate. At most add this report's URL to that
        pattern's **Seen in** (cap ~3) or sharpen its **Look for** line. This does
        **not** count as new.
      - **Genuinely new** (a new class, or a materially different detection cue or
        remediation)? Append a new `###` entry in the README format. This counts
        as **new**.
   d. Novelty bookkeeping: if this report produced ≥1 new entry (or a sharpened
      cue), set `no_new_streak = 0`; otherwise `no_new_streak += 1`.
   e. `reports_seen += 1`, `cursor = i + 1`. **Write `distill-state.json` back
      now** (so the run is resumable/interruptible).
   f. **Stop the source** when `no_new_streak >= convergence_threshold` (set
      `converged = true`) or `cursor >= count` (whole source consumed).
4. Refresh `INDEX.md` counts for touched categories.

## Discipline

- **Converge, don't accumulate.** Vuln classes repeat across audits. By report
  ~50–100 you should mostly be adding "Seen in" URLs, not new patterns — that's
  the signal to let `no_new_streak` run to the threshold and stop.
- **Instruction, not dump.** Each entry must help a future auditor *detect* and
  *fix* the issue. Drop report-specific narrative; keep the transferable cue.
- **Merge aggressively.** Prefer sharpening an existing cue over adding a 2nd
  near-identical pattern. A tight library is the whole point.
- **Provenance always.** Every pattern keeps ≥1 source URL.

## Running it

- Interactive: open this project in Claude Code and say "distill the sherlock
  knowledge" (then cyfrin).
- Headless/unattended: `python distill.py --source sherlock` then
  `python distill.py --source cyfrin` (drives Claude Code the same way `audit.py`
  does). Re-launching resumes from the saved cursor.

Process sources in order: **sherlock first, then cyfrin.** Do them one at a time.
