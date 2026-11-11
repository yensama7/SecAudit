# Distillation & audit progress — pick-up log

Durable hand-off notes so anyone can continue. Newest entry on top. The
machine-readable cursor is `distill-state.json`; this file is the human "why".

---

## Status as of 2026-11-11 (update 2 — distilled index 12–15)

### Knowledge library: 51 patterns / 13 categories (Sherlock)
Distilled from **Sherlock reports index 1–15**. New since update 1: **Sentiment
(12), Merit Circle (13), FIAT I (14), Astaria (15)**. Two new categories added —
`share-inflation` and `mev-frontrun`. See `INDEX.md` for the per-category table.

- **Sherlock cursor: 16 of 309.** `no_new_streak: 0` — still finding new patterns
  every report (these are big multi-finding reports), nowhere near convergence
  (threshold 15). Resume by distilling index 16 onward.
- **What index 12–15 added (highlights):**
  - *share-inflation* (new): first-depositor donation inflates price-per-share
    (Sentiment H-1, Merit Circle M-5 overflow variant, Astaria M-13).
  - *mev-frontrun* (new): front-run a lump-sum reward distribution (Merit Circle
    M-4); self-front-run a slash/dispute to reclaim your bond (FIAT M-5).
  - *oracle*: hard-coded decimals assumptions (Sentiment H-2..H-5, Astaria M-21);
    spot/`previewRedeem` manipulation + redemption-loss mispricing (Sentiment M-10/M-12).
  - *reentrancy*: ERC777/callback-token re-entry where code assumed plain ERC20
    (Sentiment M-6).
  - *dos*: one un-transferable asset reverts a whole liquidation/batch loop
    (Sentiment M-3).
  - *accounting*: reserve-not-excluded, pre-action check omits fee, accrue-before-
    mutate / wrapper-bypass, fee-scale (BPS vs ‰) mismatch, cancel path doesn't
    refund escrow (Sentiment M-9/M-14/M-16, FIAT M-4, Astaria H-32/H-6).
  - *signature*: `ecrecover` returns `address(0)` for bad sigs and a zeroable
    privileged slot authenticates it (Astaria H-30) — high-value classic.
  - *state-transition*: stale cached/derived value (Merit Circle H-3); improve-only
    op that degrades (Merit Circle H-1); array-index invalidation on swap-and-pop
    (Astaria H-23).
  - *input-validation*: no-op guard / missing `revert` (Sentiment M-8); inverted &
    AND-vs-OR & wrong-direction guards (FIAT H-7, Astaria H-36/H-37); hardcoded
    selector version assumptions (Sentiment M-7/M-13).
  - *token-assumption*: ERC20 semantics misuse — self-`transferFrom` needs an
    allowance, `transfer(address(0))` reverts (FIAT H-3/H-4); rebasing/airdrop
    accrual (Sentiment M-5).
  - *arithmetic*: check-after-cast is useless (FIAT M-10); round-trip precision
    loss breaks an exact-amount requirement (FIAT M-6).
- **Discipline note:** Astaria (63 findings) was heavily protocol-specific
  (liens/epochs/vaults); per "converge, don't accumulate" most findings were folded
  as `Seen in` provenance or sharpened cues rather than new `###` entries. Only
  genuinely transferable classes were added.
- **Index 10** (Sherlock's own audit PDF) still fails pypdf parse (compressed
  streams). Logged in `distill-state.json` `parse_failures`. Revisit if PyMuPDF
  installs.

### Previous status (update 1 — distilled index 1–11)
28 patterns / 11 categories from Tempus, Perennial, Flux, Flux Follow-Up, Lyra,
Hook, Opyn Crab V2, LiquiFi, Harpie. Index 9 was a duplicate Perennial re-audit
(first convergence tick, later reset). Index 10 failed to parse.

### Cyfrin: NON-DISTILLABLE (do not re-scan)
Cyfrin's public repo (`Cyfrin/cyfrin-audit-reports`, 225 PDFs) contains only
**attestation summaries** — severity counts, scope, and a hash attestation, with
**individual findings redacted** ("Technical details of individual findings are
omitted from this public summary"). Verified across indices 0, 2, 8, 20, 100,
150, 224 spanning 2023→2026. Nothing to distill. Marked `converged: true` in
`distill-state.json` so the loop skips it.

---

## What's next (in priority order)

1. **Continue Sherlock** from index 16 (`python distill.py --source sherlock`, or
   ask Claude "continue distilling sherlock"). Highest-value remaining work —
   ~293 reports left. Stop when `no_new_streak` hits 15 (convergence) or the
   source is exhausted.
2. **Add Code4rena** as a source — its public reports include full findings
   (unlike Cyfrin's summaries). Add report URLs/repo to `config/sources.yaml`
   under the `code4rena` source, then distill it the same way. This is the right
   replacement for the non-distillable Cyfrin corpus.
3. **Run real audits** with `python audit.py <github-url-or-folder>` from a plain
   terminal (not nested in a Claude Code session — the nested launcher hits a
   broken npm `claude` shim; see README). The skill reads this knowledge library
   in Stage 1 (hunting) and Stage 2 (verification).

## How distillation was actually run
Not via the nested `distill.py` headless launch (that fails on this machine: the
nested `claude-work` → `claude` resolves to a broken npm shim). Instead, done
**in-session**: Claude calls `python intelligence-engine/report_feed.py --source
<src> --index N` (allowlisted, read-only, streams+parses each report in memory),
extracts lessons, and merges them here with dedup. Both paths target the same
files; the in-session path sidesteps the launcher bug. To continue either way,
the cursor in `distill-state.json` is authoritative.

## Audit validation (done 2026-11-11)
A full pipeline run against the deliberately-vulnerable fixture
`test-targets/VulnVault/src/VulnVault.sol` produced
`test-targets/VulnVault/.security-audit/final-report.md`:
- Stage 0 discovery (`discover_sources.py`) → 1 in-scope Solidity file.
- Stage 1 → 5 findings (2 high, 1 medium, 2 low); `validate_coverage.py` and
  `validate_handoff.py` both exit 0.
- Stage 2 → each finding cross-checked against the distilled library
  (`intelligence-results.json`), 4 `confirmed` + 1 `similar_unestablished`.
- Stage 3 → `build_final_report.py` assembled the report.
Each finding maps to a knowledge pattern (reentrancy, access-control,
oracle-manipulation, token-assumption, arithmetic-rounding), proving the library
drives detection. Note: findings/intelligence here were authored in-session (the
auditor role), the same way distillation runs — not via a nested `claude-work`
launch. To re-run against a real repo: `python audit.py <github-url-or-folder>`
from a plain terminal.
