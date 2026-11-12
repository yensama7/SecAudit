# Audit Scope

> Fill this file in before running `/security-audit`. Claude reads it at the start
> of Stage 0 to narrow findings to what actually matters for this engagement.
> Delete placeholder lines rather than leaving them blank — an empty section is fine.

---

## Product description

<!-- What does this protocol do? One paragraph is enough.
     Include: what assets it handles, who the main actors are (LP, borrower,
     keeper, liquidator), and the core invariant you'd expect to always hold.

     Example:
     "Lending protocol on Arbitrum. Users deposit ERC-20 collateral, borrow
     USDC, and are liquidated when their health factor drops below 1.
     Invariant: total borrows never exceed total deposited collateral × LTV." -->

(replace this line)

---

## Chain / deployment context

- **Chain:** <!-- e.g. Ethereum mainnet / Arbitrum / Base / Solana -->
- **Compiler / runtime:** <!-- e.g. Solidity 0.8.20, Foundry; or anchor 0.29, Rust 1.76 -->
- **Key external dependencies:** <!-- e.g. Chainlink price feeds, Uniswap V3, Curve, Aave -->

---

## In scope

> List every file or directory that is explicitly in scope.
> Path is relative to the repo root. Claude will treat anything NOT listed here
> as out of scope (vendor / test / supporting infra).
>
> Example:
>   - `src/LendingPool.sol`
>   - `src/oracles/`
>   - `programs/vault/src/`

- (add paths)

---

## Out of scope

> List files, directories, or whole subsystems that are explicitly excluded.
> Common examples: mock contracts, migration scripts, governance timelock,
> a dependency you don't control (e.g. the upstream Uniswap pool itself).

- (add paths or descriptions)

---

## Trusted roles / assumptions

> List any actors or conditions Claude should treat as fully trusted and NOT
> flag as a risk. If nothing is trusted, leave this empty.
>
> Examples:
>   - "Owner / admin is a trusted multisig — owner-only privileged calls are
>     out of scope."
>   - "Users are assumed to supply correctly-encoded calldata."

- (add trust assumptions, or delete section if none)

---

## Known / intentional behaviors

> Things that look like bugs but are deliberate design choices. Claude won't
> raise them as findings.
>
> Examples:
>   - "Rounding always favours the protocol, not the user — intentional."
>   - "No slippage protection on internal swaps — handled off-chain."

- (add known behaviors, or delete section if none)

---

## Out-of-scope bug classes

> Whole classes of issues that are out of scope for this engagement.
>
> Common contest restrictions:
>   - "MEV / sandwich attacks are out of scope."
>   - "Issues requiring a compromised admin key are out of scope."
>   - "Centralization risk / no-timelock findings are informational only."
>   - "Gas optimizations are out of scope."

- (add excluded bug classes, or delete section if none)

---

## Additional context

<!-- Anything else Claude should know: links to the contest page, whitepaper,
     previous audit reports, known gotchas about a specific integration, etc. -->

(replace this line, or delete section)
