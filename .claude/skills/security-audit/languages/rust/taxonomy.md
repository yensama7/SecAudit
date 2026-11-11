# Rust vulnerability taxonomy

Covers general Rust and Solana/Anchor programs (the common competitive-audit
target). Categories are where to look, not verdicts.

## 1. Account validation (Solana — the #1 source of bugs)
- **Owner check**: is every account's `owner` verified to be the expected
  program? (Anchor `Account<T>` does this; raw `AccountInfo` does not.)
- **Signer check**: does the authority actually `is_signer`? Missing signer =
  anyone acts as that authority.
- **Writable check**: accounts mutated must be writable; attacker can pass a
  read-only or unrelated account.
- **PDA validation**: seeds + bump verified? Can an attacker substitute a PDA
  they control? Is the bump canonical (`find_program_address`)?
- **Account substitution / confused deputy**: two accounts of the same type
  swapped (e.g. pass your own vault as someone else's).
- **Account initialization**: `init` vs re-init; can an account be
  re-initialized or closed-and-revived (`close` + realloc)?
- **Type cosplay**: discriminator not checked, one account type deserialized as
  another.

## 2. Unsafe & FFI
`unsafe` blocks: invariants documented and upheld? Raw pointer deref, transmute,
`from_raw_parts`, uninitialized memory, FFI boundary assumptions. Any UB path
reachable from untrusted input.

## 3. Arithmetic
Overflow: release builds wrap silently unless `overflow-checks=true`. Use
`checked_*`/`saturating_*` for value math. Casts (`as`) truncate. Division by
zero panics. Precision/rounding in token math (same farmed-rounding risk as EVM).

## 4. Input validation & deserialization
Untrusted bytes -> `borsh`/`bincode` deserialization bounds. Length fields
trusted (allocation DoS). Index/slice out of bounds -> panic (DoS) or logic bug.
Enum/variant assumptions.

## 5. Error handling & panic
Panic/`unwrap`/`expect`/`assert` on attacker input = DoS (program aborts).
`?`-propagation that leaves state half-updated. Ignored `Result`. In Solana a
panic fails the txn but can still be a griefing/DoS vector.

## 6. Authorization & trust boundaries
Beyond signer checks: role/permission logic, who may call privileged
instructions, admin-key assumptions, whether a "trusted" account is actually
verified.

## 7. Concurrency & shared state
`Arc<Mutex<_>>` lock ordering / deadlock, data races in `unsafe`, `Send/Sync`
misuse, TOCTOU on shared state. (Less relevant for single-threaded Solana
programs; critical for off-chain services.)

## 8. Resource exhaustion / DoS
Unbounded allocation from a user-supplied size, unbounded loops, compute-budget
exhaustion on Solana, account realloc growth, recursion.

## 9. Dependency & feature config
Vulnerable crate versions (`cargo audit`), dangerous feature flags,
`default-features` pulling in unsafe paths, build-time overflow-checks setting.

## 10. CPI & program invocation (Solana)
Cross-program invocation to an unverified program id; `invoke_signed` PDA seeds
leaking authority; arbitrary CPI (attacker-specified target program); missing
program-id check on called program.
