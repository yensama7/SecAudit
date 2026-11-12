# Token behaviour assumptions — what to look for

### Raw `transfer` / `transferFrom` instead of SafeERC20 (esp. with a permissionless registry)
- **Look for:** direct `token.transfer(...)` / `transferFrom(...)` whose return
  value is ignored, on tokens that aren't guaranteed standard — especially when a
  `register()` / whitelist function lets anyone add new token/pool/AMM contracts,
  so the token set isn't known at audit time. Mixed usage (SafeERC20 for some
  tokens, raw transfers for others) is a strong tell.
- **Root cause:** assuming every token reverts on failure and returns a bool;
  non-standard tokens (no return value, fee-on-transfer, rebasing) break that,
  and a permissionless registry widens the set of tokens the code must tolerate.
- **How it's fixed:** use `SafeERC20` (`safeTransfer`/`safeTransferFrom`)
  uniformly; constrain what `register()` can add (separate registries for
  different contract kinds); account for fee-on-transfer by measuring balance
  deltas rather than trusting the amount argument.
- **Languages:** solidity
- **Typical severity:** low–high (scales with whether non-standard tokens can
  actually reach the path and whether funds are escrowed)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.02.09%20-%20Final%20-%20Tempus%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.07.05%20-%20Final%20-%20Opyn%20Squeeth%20Crab%20V2%20Audit%20Report.pdf (approve/transferFrom return ignored; fee-on-transfer unsupported) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (ERC4626 vault breaks on fee-on-transfer underlying; a claim path transfers amount 0 which reverts for some tokens) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.08%20-%20Final%20-%20Buffer%20Finance%20Audit%20Report.pdf (M-4: fee-on-transfer token makes `totalPremium` accounting wrong; M-5: raw `transfer`/`approve` without SafeERC20 — USDT returns no bool → reverts on success) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20BullvBear%20Audit%20Report.pdf (M-1: fee-on-transfer token causes shortfall when settling/reclaiming; fix: balance delta measurement) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20DODO%20Audit%20Report.pdf (M-1: raw `transferFrom` without SafeERC20 — USDT-style tokens that return no bool revert on success) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20Telcoin%20Audit%20Report.pdf (M-2: `transferFrom`/`approve` without SafeERC20 — also `approve(nonZero)` on a non-zero allowance reverts for USDT)

### Rebasing / airdrop-accruing token held via fixed share accounting → gains mis-assigned
- **Look for:** a protocol that custodies a user's token and tracks it as a fixed
  share/principal amount (lending collateral, an escrow, a vault position), where
  the token's `balanceOf` can **grow on its own** — a rebasing token (aToken,
  stETH), a token that airdrops to holders, or any positive-rebase asset. Because
  repayment/withdrawal converts shares back 1:1, the balance growth that accrued
  **while the protocol held it** is silently assigned to whoever the accounting
  credits (often the borrower, not the lender who owned the economic exposure), or
  is left stranded in the contract. Tell: integrations with known rebasing assets
  (Aave) plus accounting that never reconciles `balanceOf` against stored shares.
- **Root cause:** fixed-share bookkeeping assumes a held balance is constant;
  rebase/airdrop gains have no owner in the model, so they leak to the wrong party.
- **How it's fixed:** reconcile against live `balanceOf` (credit rebase gains to
  the rightful account), use a wrapped non-rebasing version, or explicitly
  disallow rebasing/airdrop tokens from the allowed set (and enforce that at the
  allowlist, per `access-control.md`).
- **Languages:** solidity
- **Typical severity:** low–medium (misappropriated yield/airdrop; not usually a
  direct principal loss)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf

### Two-address / proxy token bypasses an address-equality exclusion guard
- **Look for:** a guard that excludes "the protocol's own token" (or any
  disallowed token) using `tokenAddress == address(configuredToken)`. Tokens
  built on a proxy/delegate pattern (e.g. Synthetix `ProxyERC20` / `sUSD`,
  `sBTC`) have **two addresses**: the proxy and the underlying implementation.
  If `configuredToken` is set to one address but the caller passes the other,
  the equality check fails → the guard is bypassed. Canonical exploit: a
  `rescueERC20(altAddress)` call drains the stream's locked funds because the
  guard only blocked `rescueERC20(mainAddress)`.
- **Root cause:** a unique-token assumption embedded in an `==` address
  comparison; proxy-pattern tokens can reach the same balance via a different
  address.
- **How it's fixed:** instead of an address-equality guard, use a **balance
  check** — record the token balance before and after the rescue transfer and
  `require` it hasn't decreased (or hasn't decreased by more than `surplus`);
  alternatively, enumerate all known aliases of the token at the guard. For
  the stream use-case: allow rescue of the stream token only up to the amount
  above `remainingBalance`.
- **Languages:** solidity
- **Typical severity:** high (all locked/escrowed stream funds drainable)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.27%20-%20Final%20-%20Nouns%20DAO%20Audit%20Report.pdf (M-4: `rescueERC20` guard `tokenAddress == address(token())` bypassed with Synthetix ProxyERC20 alternate address)

### Misusing standard ERC20 transfer semantics (self-`transferFrom`, transfer to `address(0)`)
- **Look for:** code that moves a contract's **own** tokens with
  `token.transferFrom(address(this), to, amt)` — standard (OZ) ERC20
  `transferFrom` still spends an **allowance** keyed on `_allowances[sender]
  [msg.sender]`, so a contract moving its own balance needs to have approved
  itself; with zero allowance it **always reverts** (e.g. cancelling/refunding an
  auction can never succeed). And `token.transfer(address(0), amt)` used as a
  pseudo-"burn": OZ ERC20 `_transfer` reverts on a zero `to`, so the whole
  function (e.g. `closeAuction`) reverts forever. Tell: a contract `transferFrom`-ing
  from `address(this)`, or sending to `address(0)` to destroy tokens.
- **Root cause:** assuming `transferFrom` from self skips the allowance check, and
  that transferring to the zero address burns — neither holds for standard ERC20.
- **How it's fixed:** use `transfer`/`safeTransfer` to move the contract's own
  balance (no allowance needed); to burn, call the token's `burn`/`_burn` (or send
  to a dead address the token permits, e.g. `0x…dead`), not `address(0)`; route
  "destroyed" value to a governance/sink address if no burn exists.
- **Languages:** solidity
- **Typical severity:** high (core flow — auction close/cancel, refund — permanently
  reverts / funds stuck)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf
