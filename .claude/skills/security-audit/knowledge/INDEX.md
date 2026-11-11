# Knowledge index

Distilled vulnerability patterns by category. Maintained by the distillation
workflow (`workflows/distill-knowledge.md`). Each count is the number of
distinct `###` patterns in that category file.

| Category | Patterns | Notes |
|---|---|---|
| accounting | 8 | assets≠liabilities; swapped-from-to/wrong-key; uniqueness invariant; carved-out reserve not excluded; pre-action check omits fee; accrue-before-mutate/wrapper-bypass; fee-scale mismatch; cancel-path doesn't refund escrow |
| input-validation | 6 | admin setters missing zero/sanity + array/config invariants; zero-default id bypass; unverified caller-supplied value + caller-keyed auth; no-op guard (missing revert); inverted/AND-OR/direction guard; hardcoded selector version assumptions |
| signature-replay | 5 | off-by-one dup-skip; missing EIP-712 domain; unsigned critical field; malleability/no-nonce; ecrecover==address(0) + zero default |
| oracle-manipulation | 5 | Chainlink staleness; submitted-answer staleness; decimals assumption; spot/previewRedeem manipulation; gameable aggregation |
| access-control | 5 | permissionless mutation of others; no-timelock/EOA; inconsistent sibling auth; dead safety control; allowlist bypass via side-channel |
| state-transition | 4 | swallowed try/catch partial state; stale cached/derived value; improve-only op that degrades; array-index invalidation on reorder |
| dos | 4 | dust-deposit griefing; strict-FIFO head-of-line; ETH transfer()/send() stipend; one bad element reverts batch/liquidation |
| arithmetic-rounding | 4 | unchecked math (<0.8); round-up dust strands last withdrawer; unsafe downcast (+check-after-cast); round-trip precision breaks exact-amount |
| token-assumption | 3 | raw transfer vs SafeERC20 + open registry; rebasing/airdrop accrual; ERC20 semantics misuse (self-transferFrom / transfer-to-zero) |
| reentrancy | 3 | caller-delegated guard; cross-contract + memory-snapshot; token-callback (ERC777) re-enters |
| mev-frontrun | 2 | front-run lump-sum reward distribution; self-front-run slash/dispute to dodge bond |
| share-inflation | 1 | first-depositor donation inflates price-per-share (+pointsPerShare overflow variant) |
| initialization-upgrade | 1 | public initializer with no once-guard → proxy/beacon takeover |

**Totals:** 51 patterns / 13 categories.

_Distilled from Sherlock reports index 1–15 (Tempus, Perennial, Flux, Flux
Follow-Up, Lyra, Hook, Opyn Crab V2, LiquiFi, Harpie, Sentiment, Merit Circle,
FIAT I, Astaria; index 9 duplicate Perennial, index 10 failed to parse). Cursor
at 16 of 309, no_new_streak 0 — still finding new patterns. Continue — in a
terminal: `python distill.py --source sherlock`; or ask Claude "continue
distilling sherlock"._

## Distillation progress

Per-source cursor and convergence state live in `distill-state.json`. A source
is considered **converged** once `no_new_streak` reaches the threshold (default
15) — i.e. that many consecutive reports added no new pattern or detection cue.
