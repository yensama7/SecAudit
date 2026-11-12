# Share inflation / first-depositor — what to look for

### First depositor inflates price-per-share with a direct donation (ERC4626 / pool)
- **Look for:** a vault/pool that mints shares as
  `shares = assets * totalSupply / totalAssets()` (the classic ERC4626
  `convertToShares`, `mulDivDown(supply, totalAssets())`), where `totalAssets()`
  reads `asset.balanceOf(address(this))` (plus borrows etc.). The **first**
  depositor mints 1 wei of shares for 1 wei of assets, then **transfers a large
  amount of the asset directly to the vault** (a "donation" that bypasses
  `deposit`). Now 1 share is worth the whole balance; the next real depositor's
  `assets * 1 / hugeTotal` rounds **down to 0** (or near-0) shares — they lose
  almost their entire deposit to the attacker, who redeems the inflated share.
  Tell: `convertToShares`/`previewDeposit` with a `supply == 0 ? assets : …`
  branch and `totalAssets()` derived from live balance, no minimum-liquidity or
  dead-shares protection.
- **Root cause:** share price is computed from a balance an attacker can inflate
  out-of-band (direct transfer), and the first mint sets an attacker-chosen ratio;
  round-down on the victim's share calc completes the theft.
- **How it's fixed:** mint dead shares to a burn address / the protocol on first
  deposit (OZ's "virtual shares + virtual assets" offset, or require a minimum
  first mint and burn an initial reserve), so no single depositor can own a
  dust-sized `totalSupply`; and/or seed the pool at deployment. Measuring assets
  from an internal accounting variable instead of `balanceOf` also defeats the
  donation (a `totalAssets()` that reads live `balanceOf` is the donation vector).
- **Languages:** solidity
- **Typical severity:** high (theft of later depositors' funds)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf (first user inflates `pointsPerShare` with a huge `POINTS_MULTIPLIER` → later `_shares*pointsPerShare` overflows `int256` and every mint/burn/withdraw reverts, locking all funds — same first-depositor root cause, DoS variant; same fix: seed/dead-shares + a smaller multiplier) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (first ERC4626 depositor manipulates share price via `totalAssets` inflation) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.28%20-%20Final%20-%20Rage%20Trade%20Audit%20Report.pdf (DnGmxSeniorVault and DnGmxJuniorVault both vulnerable; guarded launch acknowledged)
