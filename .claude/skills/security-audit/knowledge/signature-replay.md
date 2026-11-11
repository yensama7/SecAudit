# Signature / replay / nonce — what to look for

### Off-by-one lets a duplicate/replay guard be skipped on the first round
- **Look for:** a duplicate-signature or replay guard gated behind a condition
  like `if (roundId > 0) { require(lastSignedRound[signer] < roundId, "dup"); }`
  while the first legitimate round uses `roundId == 0` (mismatched against a
  `latestAggregatorRoundId` that starts at 1). The guard is silently bypassed for
  the first round, so duplicate answers/signatures are accepted there.
- **Root cause:** an index/id convention mismatch (0-based vs 1-based) causes the
  boundary case to fall outside the guard's range.
- **How it's fixed:** sync the id conventions so the guard covers every round
  (`require(latestRound() + 1 == roundId)`), making the `> 0` special-case
  unnecessary; add a test for the very first round specifically.
- **Languages:** solidity
- **Typical severity:** medium (replay/duplicate submission in the boundary case)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.06%20-%20Final%20-%20Flux%20Audit%20Report.pdf

### Signed message omits a domain separator → cross-chain / cross-contract replay
- **Look for:** signatures built with `toEthSignedMessageHash` / a raw
  `keccak256` of the payload that does **not** bind `chainid`, the verifying
  contract address, and a name/version (i.e. not EIP-712 `toTypedDataHash` with a
  domain separator). If the same contract is deployed on multiple chains (or the
  payload lacks a nonce/verifying-contract binding), a signature valid on one can
  be replayed on another — or on a sibling contract.
- **Root cause:** the signed digest isn't scoped to where it's meant to be used;
  domain (chainid + contract + nonce) is missing from what's signed.
- **How it's fixed:** sign an EIP-712 typed-data hash that includes a domain
  separator (`chainId`, `verifyingContract`, name, version) and a per-use nonce;
  reject digests that don't match the local domain. (Only skip if cross-chain
  replay is explicitly the intended "sign once, sync everywhere" behaviour.)
- **Languages:** solidity
- **Typical severity:** low–high (depends on what the signature authorizes and
  whether sibling deployments exist)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.18%20-%20Final%20-%20Flux%20Follow-Up%20Audit%20Report.pdf

### Security-critical parameter left out of the signed payload (MITM can alter it)
- **Look for:** a function authorized by a signature where a value that controls
  economics or authorization (strike price, amount, recipient, deadline, fee) is
  passed as a **separate calldata argument** and is **not** part of what was
  signed/verified. A front-runner replays the valid signature while swapping that
  unsigned argument (e.g. strike 120 → 1), and the check still passes.
- **Root cause:** the signature binds only some fields; the rest are trusted from
  calldata, so they're malleable by anyone who relays the tx.
- **How it's fixed:** include every security-relevant parameter in the signed
  message (and verify it), so changing any of them invalidates the signature.
- **Languages:** solidity
- **Typical severity:** high (forced mispricing / value theft)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.30%20-%20Final%20-%20Hook%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (lien type `nlrType` omitted from the strategist-signed payload, so a borrower swaps the loan terms struct)

### ECDSA signature malleability / no nonce → replay of a superseded signed action
- **Look for:** signature verification via raw `ecrecover` or OpenZeppelin
  `ECDSA.recover` on **old OZ (< 4.7.3)**, where the signature bytes themselves
  are used as the replay key and there's **no incrementing nonce** in the signed
  data. A malleable second signature (s/v variant) for the same message passes the
  "already used?" check, and without a nonce an old, superseded request (e.g. a
  previous `changeRecipientAddress`) can be re-submitted and take effect.
- **Root cause:** using the signature as an identity (malleable) instead of a
  message nonce; outdated ECDSA lib lacking the malleability guard.
- **How it's fixed:** upgrade OZ (≥ 4.7.3) / enforce low-`s`; include and check an
  **incrementing nonce** (and chainId + verifying contract) in the signed payload
  so each signed action is single-use and ordered. Also verify a signer-controlled
  **nonce is actually read/enforced** — a declared nonce that the verifier never
  checks means a strategist/signer can't cancel or invalidate an outstanding signed
  commitment (it stays valid forever).
- **Languages:** solidity
- **Typical severity:** medium–high (replay of a sensitive action → fund loss)
- **Seen also:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (strategist nonce never checked → signed commitments cannot be cancelled)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.12%20-%20Final%20-%20Harpie%20Audit%20Report.pdf

### `ecrecover` returns `address(0)` for a bad signature, and a privileged slot defaults to `address(0)`
- **Look for:** raw `ecrecover(hash, v, r, s)` whose result is compared to an
  authorized address **without** a `require(recovered != address(0))` guard —
  dangerous when an authorized/privileged variable can itself be `address(0)`
  (an unset `delegate`/`signer`/`owner` that the setter *skips* assigning when
  passed zero: `if (x != address(0)) delegate = x;`). An attacker supplies a
  **malformed** signature (e.g. `v` not 27/28, or garbage `r/s`) so `ecrecover`
  returns `address(0)`, and sets the claimed signer to `address(0)` too — now
  `recovered == strategist` **and** `recovered == delegate` both hold, so arbitrary
  parameters validate and the vault/contract is drained.
- **Root cause:** `ecrecover`'s "invalid → `address(0)`" sentinel collides with an
  uninitialized/zeroable privileged address; neither is excluded, so the zero case
  authenticates.
- **How it's fixed:** always `require(recovered != address(0))` after `ecrecover`
  (or use OZ `ECDSA.recover`, which reverts on zero/invalid); never leave a
  privileged address at the default `address(0)` (set a sane default or revert if
  unset); reject signatures whose signer is the zero address.
- **Languages:** solidity
- **Typical severity:** high–critical (auth bypass → full fund theft)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf
