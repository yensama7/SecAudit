# Knowledge index

Distilled vulnerability patterns by category. Maintained by the distillation
workflow (`workflows/distill-knowledge.md`). Each count is the number of
distinct `###` patterns in that category file.

| Category | Patterns | Notes |
|---|---|---|
| accounting | 11 | assets≠liabilities; swapped-from-to/wrong-key; uniqueness invariant; carved-out reserve not excluded; pre-action check omits fee; accrue-before-mutate/wrapper-bypass; fee-scale mismatch; cancel-path doesn't refund escrow; unstake recomputes instead of stored original; balance-delta measures wrong asset representation; async pending outflow stales NAV |
| input-validation | 7 | admin setters missing zero/sanity + array/config invariants (+ init/update asymmetry + unbounded user time + embedded decimals assumption); zero-default id bypass (+sentinel reset by user); unverified caller-supplied value + caller-keyed auth; no-op guard (missing revert); inverted/AND-OR/direction guard; hardcoded selector version assumptions; only-zero guard on partial fulfillment |
| signature-replay | 6 | off-by-one dup-skip; missing EIP-712 domain (+no expiration); abi.encodePacked dynamic-type collision; unsigned critical field; malleability/no-nonce; ecrecover==address(0) + zero default |
| oracle-manipulation | 5 | Chainlink staleness (+L2 sequencer uptime + multi-phase sync revert); submitted-answer staleness; decimals assumption (+non-token decimals applied to wrong token); spot/previewRedeem manipulation (+wrong caller arg); gameable aggregation |
| access-control | 7 | permissionless mutation of others; no-timelock/EOA; inconsistent sibling auth; dead safety control; allowlist bypass via side-channel; hasRole() catch-all defeats freeze; caller-supplied from drains approved tokens |
| state-transition | 5 | swallowed try/catch partial state; stale cached/derived value; improve-only op that degrades; array-index invalidation on reorder; validate-before-normalize rounds into invalid range |
| dos | 5 | dust-deposit griefing; strict-FIFO head-of-line; ETH transfer()/send() stipend; one bad element reverts batch/liquidation (+ECDSA.recover + safeTransferFrom callback gas); ghost-entry queue bloat |
| arithmetic-rounding | 6 | unchecked math (<0.8); round-up dust strands last withdrawer; unsafe downcast (+check-after-cast); round-trip precision breaks exact-amount; divide-before-multiply truncates to zero; proportional N-way split floors each bucket |
| token-assumption | 4 | raw transfer vs SafeERC20 + open registry; rebasing/airdrop accrual; ERC20 semantics misuse (self-transferFrom / transfer-to-zero); two-address proxy token bypasses address equality guard |
| reentrancy | 4 | caller-delegated guard; cross-contract + memory-snapshot; token-callback (ERC777/ERC721 _safeMint) re-enters; read-only reentrancy (state updated after callback) |
| mev-frontrun | 3 | front-run lump-sum reward distribution; self-front-run slash/dispute to dodge bond; same-block flashloan checkpoint gaming |
| share-inflation | 1 | first-depositor donation inflates price-per-share (+pointsPerShare overflow variant) |
| initialization-upgrade | 1 | public initializer with no once-guard → proxy/beacon takeover |

**Totals:** 65 patterns / 13 categories.

_Distilled from Sherlock reports index 1–31 (Tempus, Perennial, Flux, Flux
Follow-Up, Lyra, Hook, Opyn Crab V2, LiquiFi, Harpie, Sentiment, Merit Circle,
FIAT I, Astaria, NFTPort, Mover, Rage Trade, Bond Protocol, Frankendao, Buffer
Finance, Opyn Crab Netting, BullvBear, DODO, Telcoin, Nouns DAO, Sentiment
January Update, Perennial December Update, Lyra 2023.01.24, Sentiment December
Update; index 9 duplicate Perennial, index 10 failed to parse). Cursor at 32 of
309, no_new_streak 0 — still finding new patterns. Continue — ask Claude
"continue distilling sherlock"._

## Distillation progress

Per-source cursor and convergence state live in `distill-state.json`. A source
is considered **converged** once `no_new_streak` reaches the threshold (default
15) — i.e. that many consecutive reports added no new pattern or detection cue.
