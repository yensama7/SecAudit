# Access control / authorization — what to look for

### Permissionless function mutates another account's state with adverse side effects
- **Look for:** a state-changing function (settlement, "poke", harvest,
  liquidate-trigger, `settleAccount(addr)`) callable by **anyone** on **any**
  account, where the mutation changes that account's risk posture — e.g. forcing
  realized PnL/interest onto a position so it crosses a liquidation threshold at
  an attacker-chosen moment. The victim never acted; a third party moved their
  state.
- **Root cause:** convenience-permissionless entry points that were only meant to
  be triggered by the account owner's own actions; the timing/side-effect on
  others wasn't modeled.
- **How it's fixed:** restrict the entry point to the account owner or internal
  position-change flows; and/or make downstream checks (e.g. maintenance) use only
  already-settled state so an external poke can't change the outcome.
- **Languages:** solidity
- **Typical severity:** medium–high (unexpected liquidation / value extraction)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.02%20-%20Preliminary%20-%20Perennial%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (`_deleteLienPosition`/`transferWithdrawReserve`/`LiquidationAccountant.claim` callable by anyone → lien removal, repeated reserve transfer, forced value drop)

### Privileged role changes critical params instantly (no timelock, EOA-ownable)
- **Look for:** `onlyOwner`/`onlyAdmin` setters for fees, maintenance ratios,
  min-collateral, oracle/implementation addresses that take effect **immediately**
  with no timelock and no upper/lower bounds, and an owner that can be a single
  EOA. Raising maintenance can force instant liquidations; swapping an
  implementation/oracle address can redirect funds; raising min-collateral can DoS
  deposits/withdrawals.
- **Root cause:** centralization + no delay means a compromised/malicious (or
  merely hasty) admin can harm users before they can react, and users can't exit.
- **How it's fixed:** route privileged setters through a `TimelockController` (or
  equivalent delay), bound parameter ranges and max step sizes, emit events, and
  require a multisig (never an EOA) for the owner role.
- **Languages:** solidity
- **Typical severity:** low–medium (centralization risk; impact depends on the knob)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.02%20-%20Preliminary%20-%20Perennial%20Audit%20Report.pdf

### Inconsistent authorization across sibling entry points (one checks the caller, the twin doesn't)
- **Look for:** several functions that reach the same privileged internal action
  by different routes (e.g. `mintWithERC721` vs `mintWithVault` vs
  `mintWithEntitledVault`), where **one** enforces `caller == owner/operator` and
  the **others don't**. The callee often *assumes* the caller was already
  authorized (a code comment like "if msg.sender != tokenOwner, approve
  msg.sender…"), but one entry point never established that. An attacker front-runs
  / replays the unguarded path to mint/act on someone else's asset, or sets an
  attacker-favorable parameter (e.g. a 1-wei strike) and pockets the spread.
- **Root cause:** the authorization invariant is enforced per-entry-point instead
  of centrally; a newer/alternate path skips the check its sibling performs.
- **How it's fixed:** enforce the owner/operator check in the shared callee (or in
  every entry point identically); don't rely on a comment-level assumption that
  "the caller already had the right." Add an invariant test that each entry point
  rejects a non-owner caller.
- **Languages:** solidity
- **Typical severity:** high (asset theft / forced mispricing)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.30%20-%20Final%20-%20Hook%20Audit%20Report.pdf

### Declared safety control with no activation path (dead pause / guard)
- **Look for:** a contract that inherits a control mechanism and gates functions
  with its modifier — `PausableUpgradeable` + `whenNotPaused`, a `whenNotFrozen`
  flag, an allowlist gate — but **never exposes a way to engage it** (no public
  `pause()`/`unpause()` calling the internal `_pause()`, no setter for the flag).
  The guard looks protective but can never actually fire, so the "emergency stop"
  doesn't exist. Inverse also worth checking: a one-way flag (`freeze`) callable
  repeatedly or with no effect.
- **Root cause:** the modifier/inheritance was added but the activation wiring
  was omitted — a safety control that is present in form only.
- **How it's fixed:** expose the activation path (access-controlled `pause()` /
  `unpause()` → `_pause()`/`_unpause()`, or a setter for the gating flag); add a
  test that actually pauses and asserts the gated functions revert.
- **Languages:** solidity
- **Typical severity:** low–medium (no emergency response when needed; impact
  surfaces only during an incident)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.08.24%20-%20Final%20-%20LiquiFi%20Audit%20Report.pdf

### Allowlist enforced at the front door but bypassed via a side entry into the same state
- **Look for:** a whitelist/eligibility check (`isCollateralAllowed`,
  `isTokenAllowed`, KYC/cap gate) enforced in the **obvious** entry point
  (`deposit`, `add`) but **not** on the other ways the same protected state gets
  mutated. Side doors to hunt: (a) **reward/LP-exit paths** that push arbitrary
  tokens in — e.g. Curve/Uniswap `removeLiquidity` returns the pair tokens and the
  code registers them as account assets with no allow-check; (b) **direct
  transfers** to a contract whose health/value is computed from `balanceOf`, so a
  user who already holds a **delisted** asset keeps using it by transferring more
  straight in (bypassing the now-blocked `deposit`); (c) claim-rewards that add
  non-whitelisted tokens. If merely having an **oracle** set (without being on the
  collateral allowlist) is enough to count an asset, an admin "set oracle but don't
  enable yet" step becomes exploitable.
- **Root cause:** the allowlist invariant is checked per-entry-point instead of at
  the single chokepoint where an asset becomes counted/usable; alternate state
  mutations were not modeled as entry points.
- **How it's fixed:** enforce the allow-check at the **chokepoint** that registers
  the asset / computes health (`_updateTokensIn`, the asset-registration helper),
  not only in `deposit`; for delisting, split health math so a delisted asset is
  ignored for *new* borrowing but still counted for liquidation; don't infer
  eligibility from "an oracle exists."
- **Languages:** solidity
- **Typical severity:** high (price-manipulatable/unvetted token used as collateral
  → protocol drain)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf
