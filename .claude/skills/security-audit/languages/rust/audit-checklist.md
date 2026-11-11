# Rust / Solana audit checklist

## Per program / crate
- [ ] What are the instructions / public entry points and their invariants?
- [ ] Which accounts does each instruction touch, and what are the required
      constraints on each?
- [ ] Where does value (lamports / SPL tokens) move?
- [ ] Admin / authority keys and exactly what they control.

## Solana account checks (per instruction, per account)
- [ ] Owner verified (expected program) — not a bare `AccountInfo`.
- [ ] Signer verified where authority is required (`is_signer`).
- [ ] Writable verified for every mutated account.
- [ ] PDA seeds + canonical bump verified; attacker can't substitute a PDA.
- [ ] Account type discriminator checked (no type cosplay).
- [ ] No account substitution / confused-deputy between same-type accounts.
- [ ] `init` can't be re-run; close can't be followed by revive.
- [ ] CPI target program id verified; `invoke_signed` seeds don't over-grant.

## General Rust
- [ ] Value arithmetic uses `checked_/saturating_`; `as` casts don't truncate
      attacker input; no div-by-zero on user input.
- [ ] No `unwrap/expect/panic/assert/indexing` reachable from untrusted input on
      a critical path (DoS).
- [ ] `unsafe` blocks: invariants hold; no UB from untrusted input.
- [ ] Deserialization bounds-checked; length/size fields not blindly trusted.
- [ ] State isn't left half-updated on early `?`-return.
- [ ] `overflow-checks` on for release, or all value math uses checked ops.
- [ ] `cargo audit` clean / no known-vuln deps; feature flags sane.

## Coverage
- [ ] Mark file `examined` in coverage.json with unresolved questions.

Anchor note: `#[account(...)]` constraints (`has_one`, `seeds`, `bump`,
`owner`, `signer`, `constraint = ...`) do a lot of this — verify the constraints
are actually present and correct, not just that Anchor is used.
