# Denial of service / griefing — what to look for

### Dust deposit front-run breaks a minimum-balance invariant on withdrawal
- **Look for:** a withdraw path guarded by an "account is empty OR above
  `minCollateral`/`minBalance`" invariant, combined with a deposit path that lets
  **anyone** credit **any** address with **no minimum**. An attacker front-runs
  the victim's full withdrawal with a 1-wei deposit, so the post-withdraw balance
  is non-zero but below the minimum → the withdrawal reverts. Repeatable =
  permanent lockout of funds.
- **Root cause:** an invariant enforced symmetrically on withdrawal but not on
  deposit; third parties can perturb another account's state for free.
- **How it's fixed:** require `depositTo(other) >= minCollateral` when depositing
  to an account you don't own (or disallow third-party deposits); alternatively
  let the owner always withdraw to zero regardless of the minimum.
- **Languages:** solidity
- **Typical severity:** medium (griefing / temporary-to-persistent DoS; no direct theft)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.02%20-%20Preliminary%20-%20Perennial%20Audit%20Report.pdf

### Strict-FIFO queue: one un-processable entry blocks everyone behind it
- **Look for:** a two-step deposit/withdrawal (or generic job) queue that must be
  processed **in chronological order** — `processQueue` handles the head, not an
  arbitrary id. If the head entry can revert or early-return indefinitely (e.g.
  `totalTokensBurnable == 0`, a failing external call, an unmet condition), the
  whole queue wedges and no later entry can ever be processed.
- **Root cause:** coupling liveness of all entries to the processability of the
  oldest one; no way to skip, cancel, or independently process a stuck entry.
- **How it's fixed:** let entries be processed/claimed independently (by id), or
  allow a stuck head to be skipped/cancelled after a timeout; isolate failures so
  one bad entry can't freeze the queue. (A privileged guardian fallback to drain
  the queue is a mitigation, not a fix.)
- **Languages:** solidity
- **Typical severity:** medium–high (funds frozen / protocol-wide DoS)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.27%20-%20Final%20-%20Lyra%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.09%20-%20Final%20-%20Opyn%20Crab%20Netting%20Audit%20Report.pdf (M-2: `userDepositsIndex`/`userWithdrawsIndex` per-user arrays grow indefinitely because deletes zero entries rather than removing them, so the linear scan grows unboundedly) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Lyra%20Audit%20Report.pdf (H-4: `processWithdrawalQueue` processes in strict chronological order; a USDC-blacklisted beneficiary causes `_transferQuote` to revert → all later withdrawals in the queue are permanently frozen)

### ETH sent via `transfer()` / `send()` (2300-gas stipend) reverts for contract recipients
- **Look for:** native-ETH payouts using `payable(to).transfer(amt)` or
  `to.send(amt)` (fee withdrawals, refunds, claims). The 2300-gas stipend reverts
  if the recipient is a contract with a non-trivial `receive()`/fallback (e.g. a
  multisig, smart-contract wallet, or a proxy that adds call overhead), so that
  recipient can never withdraw.
- **Root cause:** relying on the fixed 2300-gas stipend (an outdated reentrancy
  defense) assumes all recipients are EOAs or cheap fallbacks.
- **How it's fixed:** use `(bool ok, ) = to.call{value: amt}(""); require(ok);`
  and guard reentrancy with CEI + a `nonReentrant` lock instead of the gas
  stipend. (Consider a pull-payment pattern for untrusted recipients.)
- **Languages:** solidity
- **Typical severity:** medium (recipient-specific DoS of withdrawals; recoverable
  if the recipient can change address)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.12%20-%20Final%20-%20Harpie%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20DODO%20Audit%20Report.pdf (M-4: `payable(addr).transfer(amount)` for ETH fee and return transfers) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Lyra%20Audit%20Report.pdf (M-1: `payable(msg.sender).transfer(address(this).balance)` returns excess ETH to caller after a hedge operation → smart-contract callers with a non-trivial `receive()` revert → excess ETH locked in the hedger)

### Unbounded ghost-entry accumulation turns a queue into a gas DoS
- **Look for:** a queue/array where entries can be "deleted" by **zeroing out**
  rather than truly removing (e.g. `delete queue[i]` or `queue[i] = 0` sets the
  slot to its zero value but the slot still exists). An attacker who can cheaply
  create many entries and then zero them out leaves a trail of blank slots that any
  `while`/`for` loop must still iterate over. If the loop can't skip blank entries
  without spending significant gas, an attacker can grow the queue to the point
  where any real work (processing, claiming, auctioning) hits the block gas limit.
  Related: per-user index arrays (`userDepositsIndex[]`) that only zero entries on
  delete — scanning them becomes unbounded as a user deposits/withdraws repeatedly.
- **Root cause:** soft-delete (zeroing) rather than hard-delete (pop/swap) means
  the array's length grows monotonically; nothing reclaims the freed space, so the
  scan grows with the total ever-added count, not the current count.
- **How it's fixed:** compact the array on removal — swap the deleted element with
  the last one and `pop()` the last slot (O(1)); or maintain a separate head/tail
  pointer so only live entries are iterated; cap the number of entries a single
  account can create to limit the attack surface.
- **Languages:** solidity
- **Typical severity:** medium–high (gas DoS on critical protocol path; auctions /
  withdrawals become permanently inoperable above attacker-chosen cost)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.09%20-%20Final%20-%20Opyn%20Crab%20Netting%20Audit%20Report.pdf (H-3: attacker creates many deposits, dequeues them → blank entries accumulate → `while` loop must skip all blanks → block gas limit hit)

### One un-transferable asset in a loop blocks a whole batch operation (esp. liquidation)
- **Look for:** a critical function that iterates a collection and transfers each
  item, where **any single** failing transfer reverts the entire call — most
  dangerously a `liquidate`/`sweepTo` that loops over an account's asset list. A
  transfer can fail for many reasons: a token that **reverts on zero-value**
  transfers (and a 0-balance asset is still listed — e.g. a 0-amount swap/deposit
  left it there), a **blacklist** (USDC/USDT can freeze an address), a **paused**
  token, or an **upgradeable** token that changed behaviour. The borrower can even
  deliberately get itself blacklisted to become **unliquidatable**, so bad debt
  sits forever. Same shape bricks any "distribute to everyone" / batch-claim loop.
  Also watch: (a) **`ECDSA.recover()` called in a loop that uses `continue` on
  invalid sig** — the function reverts on malformed signatures (not just returns a
  wrong address), breaking the intended non-atomic loop for any malformed entry;
  swap to `ECDSA.tryRecover()`. (b) **`safeTransferFrom` to untrusted contract
  recipients** (even a single one, outside a loop) triggers `onERC721Received`
  which the recipient can use to consume all gas → the outer call reverts;
  wrap the transfer in `try/catch` to handle the failure gracefully.
- **Root cause:** all-or-nothing batching couples the liveness of the whole
  operation to the one most fragile element; weird-ERC20 behaviours (see
  `token-assumption.md`) aren't tolerated, and dead/zero-balance entries aren't
  pruned.
- **How it's fixed:** isolate per-item failure — wrap each transfer in
  `try/catch` and skip (optionally keep the asset for a later retry); let items be
  processed/claimed individually rather than as one atomic batch; prune
  zero-balance assets so they can't wedge the loop; use pull-payments for untrusted
  recipients; use `tryRecover` for signature validation inside loops.
- **Languages:** solidity
- **Typical severity:** medium–high (unliquidatable accounts / frozen batch; can be
  attacker-triggered to dodge liquidation)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.08%20-%20Final%20-%20Buffer%20Finance%20Audit%20Report.pdf (M-3: `ECDSA.recover` reverts on malformed sig, breaking non-atomic loop) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.09%20-%20Final%20-%20Opyn%20Crab%20Netting%20Audit%20Report.pdf (H-2: blacklisted USDC recipient in sequential withdrawal queue freezes the entire auction; M-4: one bad order — revoked approval, used nonce, insufficient balance — reverts entire auction batch) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.12%20-%20Final%20-%20Telcoin%20Audit%20Report.pdf (M-6: a failing plugin claim reverts the entire `slash()` → slashed user can exit during the window) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.12.27%20-%20Final%20-%20Nouns%20DAO%20Audit%20Report.pdf (M-6: blacklisted USDC recipient blocks stream `cancel()` → payer can't reclaim future funds) ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2023.01.24%20-%20Final%20-%20Lyra%20Audit%20Report.pdf (H-4: `processWithdrawalQueue()` calls `_transferQuote(beneficiary, amount)` with no try/catch → a USDC-blacklisted beneficiary causes revert → all subsequent withdrawals permanently blocked)
