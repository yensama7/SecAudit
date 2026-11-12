# MEV / front-running — what to look for

### Front-run a lump-sum reward/fee distribution to snipe a pro-rata share
- **Look for:** a function that drops a batch of rewards/fees onto **current**
  stakers in one shot — `distributeRewards(amount)` that bumps a global
  `pointsPerShare += amount * MULT / totalShares`, `notifyReward` that credits the
  present balance, an airdrop/`rebase` split by current holdings. Because the
  entitlement is a snapshot at distribution time, anyone can deposit a large stake
  **right before** the distribution tx, capture a big slice of it, and withdraw
  **right after**, without having staked through the earning period. A public/
  predictable trigger (or a mempool-visible top-up) makes it trivial; even with a
  `MIN_LOCK_DURATION`, well-capitalized actors can still do it (flash-loan only if
  there's no lock).
- **Root cause:** rewards are allocated by an instantaneous share snapshot rather
  than by time-weighted participation, so stake acquired for one block earns like
  stake held for the whole period.
- **How it's fixed:** stream rewards gradually over time (Synthetix
  `StakingRewards` `rewardRate` / `periodFinish` model) so a one-block deposit
  earns ~nothing; accrue by time-weighted balance; and/or impose a lock between
  deposit and reward eligibility. Avoid predictable one-shot distributions keyed on
  the current snapshot.
- **Languages:** solidity
- **Typical severity:** medium–high (theft of a large fraction of each distribution)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.04%20-%20Final%20-%20Merit%20Circle%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.22%20-%20Final%20-%20Perennial%20December%20Update%20Audit%20Report.pdf (M-2: synchronous vault atop asynchronous underlying — attacker front-runs price-settlement tx, deposits to capture PnL, exits right after) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Lyra%20Audit%20Report.pdf (M-2: attacker back-runs a large `initiateDeposit` with `processDepositQueue() + settleExpiredBoard()` in one tx — processing the deposit temporarily inflates NAV which raises `longScaleFactor` → board payouts favor the attacker at the expense of other boards)

### Same-block flashloan gaming of checkpoint/snapshot-based weights
- **Look for:** a staking/governance/reward system that records a user's
  balance as an on-chain checkpoint and later queries it with `getAtBlock(N)`.
  If the checkpoint library returns the **first** entry in block N (rather than
  the last), an attacker can: (1) flashloan a large token amount, (2) stake in
  the same block (creates checkpoint[0] = high), (3) exit in the same block
  (creates checkpoint[1] = 0), (4) repay the flashloan — all in one tx. When
  the system later calls `getAtBlock(N)` it reads checkpoint[0] (the high value)
  rather than the final checkpoint[1], crediting the attacker with a stake they
  never held past that block. Even without a checkpoint bug, **same-block**
  stake+exit lets anyone game systems that read the snapshot of block N at the
  *start* of block N+1 without a lock.
- **Root cause:** snapshot taken at a block height the attacker can influence
  within one transaction; no requirement that stake persists until the next block.
- **How it's fixed:** require that exits are in a **later block** than the entry
  (`require(block.number > lastStakeBlock)`); use the **latest** checkpoint for
  current-block queries, not an earliest-in-block lookup; or move to
  time-weighted-average balance (can't be gamed in one block). Audit `getAtBlock`
  / `getPriorVotes` for same-block edge cases.
- **Languages:** solidity
- **Typical severity:** medium (fake stake captures reward share; slashing avoidance)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20Telcoin%20Audit%20Report.pdf (M-1: OZ Checkpoints `getAtBlock` returns first same-block entry; flashloan stake→exit in one block fakes high snapshot)

### Self-front-run a permissionless slash/dispute to dodge the bond penalty
- **Look for:** a bond/stake-backed honesty mechanism where a **permissionless**
  function (`dispute()`, `liquidate()`, `challenge()`) pays the full bond/reward to
  whoever calls it first, and the offender can call it **on their own** malicious
  position. A dishonest proposer who sees a dispute in the mempool front-runs it,
  disputing themselves so the bond returns to them (or to an address they control)
  and the honest challenger's tx reverts, wasting their gas. Repeated, this pushes
  honest keeper/dispute bots out (they keep losing gas), after which the attacker
  can submit bad data that goes unchallenged. Tell: the penalty is "lose the bond
  to the disputer," the disputer can be the proposer, and 100% of the bond is
  recoverable by self-disputing.
- **Root cause:** the deterrent assumes the offender can't be the one who triggers
  the penalty; a permissionless, winner-takes-the-bond design lets them reclaim it
  and grief real challengers via ordering.
- **How it's fixed:** make the penalty bite regardless of who disputes — burn or
  escrow a portion of the bond (pay the disputer only part, send the rest to the
  protocol/an honest-proposer pool) so a self-dispute still costs the offender;
  restrict re-bonding by slashed proposers; make failed disputes cheap (revert
  early) so griefing is less effective.
- **Languages:** solidity
- **Typical severity:** medium–high (bond deterrent neutralized → bad data accepted)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.09%20-%20Final%20-%20FIAT%20I%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20Telcoin%20Audit%20Report.pdf (M-5: `slash()` is permissionless → malicious staker frontruns it with `fullClaimAndExit()` to leave with their funds before the penalty lands)
