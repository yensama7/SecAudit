# Oracle manipulation / bad data — what to look for

### Chainlink `latestRoundData()` consumed without staleness / completeness checks
- **Look for:** a call like `(, int256 price, , , ) = aggregator.latestRoundData();`
  that destructures away `updatedAt` and `answeredInRound` (the commas) and uses
  `price` directly. No check that the round completed or is fresh. Also watch for
  missing `price > 0` checks and hardcoded feed/ENS addresses.
- **Root cause:** trusting the oracle return without validating the round — a
  stale or incomplete round returns a last-known or zero value the protocol then
  treats as current.
- **How it's fixed:** capture `roundId`, `updatedAt`, `answeredInRound` and
  `require(updatedAt != 0, "round not complete")`,
  `require(answeredInRound >= roundId, "stale price")`, and `require(price > 0)`;
  consider a max-staleness window. Inject feed addresses via constructor, not
  hardcoded constants.
- **Languages:** solidity
- **Typical severity:** low–high (here low — the feed was only used for stats;
  severity scales with how load-bearing the price is)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.02.09%20-%20Final%20-%20Tempus%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.06%20-%20Final%20-%20Flux%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf

### Submitted/aggregated answers stamped "fresh" without a signed per-answer timestamp
- **Look for:** a first-party / push oracle where off-chain signers submit
  answers that get aggregated and stored with `block.timestamp` as the time —
  but each answer's own observation time is **not** part of the signed payload
  and not checked. A delayed/withheld `transmit` tx then records stale values as
  current. Also: a reader returning `(0, success)` for a not-yet-set id instead
  of signalling "no data".
- **Root cause:** freshness assumed from submission time rather than proven from
  the data; missing-data not distinguished from zero.
- **How it's fixed:** include each observation's timestamp in the signed message
  and check it against `block.timestamp` with a max-staleness bound; return an
  explicit not-available status (not `0`/success) when no value exists.
- **Languages:** solidity
- **Typical severity:** high (stale price drives money-market liquidations/mints)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.06%20-%20Final%20-%20Flux%20Audit%20Report.pdf

### Price math hard-codes a decimals assumption (feed / token / vault / LP)
- **Look for:** price/value calculations that bake in a fixed decimal count
  instead of reading it. Concrete shapes: (a) `(uint(answer)*1e18)/ethPrice`
  assuming every Chainlink feed returns **8** decimals (AMPL/USD is 18) or that
  token and ETH feeds share decimals; (b) `rate.mulDivDown(1e8, token.decimals())`
  where someone forgot `10 **` so it divides by the *count* (e.g. 18) not
  `1e18`; (c) an ERC4626 oracle using `vault.decimals()` as the underlying's
  decimals (EIP-4626 does **not** require them to match); (d) a UniV2 LP
  fair-price formula assuming both reserves are 18-decimal (USDC is 6). Any of
  these makes `getPrice` off by orders of magnitude → borrow against hugely
  over/under-valued collateral and drain the protocol.
- **Root cause:** a decimals value is assumed constant (8, or 18, or
  "vault == underlying") rather than queried from the specific token/feed; a
  `10 ** decimals` is dropped so a raw count is used as a scale factor.
- **How it's fixed:** query decimals from each party — `feed.decimals()`,
  `IERC20Metadata(underlying).decimals()` — and scale by `10 ** d`; for ERC4626
  use the **asset's** decimals, not the vault's; normalize all reserves to a
  common scale before the LP formula; `require(feed.decimals() == 8)` at
  registration if the code truly only supports 8.
- **Languages:** solidity
- **Typical severity:** high (mispriced collateral → protocol drain)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf ; https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.11.10%20-%20Final%20-%20Astaria%20Audit%20Report.pdf (arithmetic assumes the underlying token always has 18 decimals)

### Spot exchange-rate / `previewRedeem` used as a price → single-block manipulation
- **Look for:** an oracle that derives a price from an instantaneous on-chain
  reading an attacker can move within one transaction: `vault.previewRedeem(1e18)`
  / `convertToAssets` (ERC4626 share price = live `totalAssets/totalSupply`),
  spot AMM reserves, or `getReserves()` without a time-weighted average. Deposit/
  mint/withdraw into the vault (or swap into the pool) in the same tx to inflate
  or deflate the reported price, then borrow more than backing or liquidate a
  victim. Related: a redemption-value quote (`previewRedeem(10**decimals)`) that
  ignores **withdrawal loss/slippage** for large amounts — a levered/multi-strategy
  vault returns less on a real large redemption than the small-unit quote implied,
  so the protocol lends against value it can't actually liquidate.
- **Root cause:** using a manipulable spot/marginal quantity as a price feed, and
  assuming the marginal exchange rate scales linearly to the full liquidatable
  amount.
- **How it's fixed:** use a manipulation-resistant price (TWAP, or an independent
  Chainlink-style feed) rather than a spot pool/vault read; for redemption-based
  pricing, price the **actual** amount to be liquidated (and/or cap LTV hard for
  assets whose exit value is slippage/loss-sensitive).
- **Languages:** solidity
- **Typical severity:** high (borrow against inflated collateral / unfair liquidation)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.10.18%20-%20Final%20-%20Sentiment%20Audit%20Report.pdf

### Gameable aggregation: permissionless submit lets an attacker pick the answer subset
- **Look for:** an aggregate (median/mean) computed from whatever signed answers
  the **caller** chooses to include, where `transmit`/submit is callable by
  anyone as long as ≥ `minSigners` signatures are present. An attacker watches
  the mempool, drops the answers that don't suit them, and submits only a
  minimal subset to move the median. Compounding risk: any address granted a
  privileged `VALIDATOR_ROLE` can bypass the whole aggregation and post a single
  arbitrary answer.
- **Root cause:** the aggregate's integrity depends on *who assembles the inputs*,
  but input assembly is permissionless and the signer set vs. `minSigners` gap is
  large; a bypass role defeats the multi-party assumption.
- **How it's fixed:** permission submission to validators only (with a slashing/
  penalty mechanism), require all signers for a round or bound `signers −
  minSigners`, and remove/lock down any role that can bypass aggregation.
- **Languages:** solidity
- **Typical severity:** high (price manipulation)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.06%20-%20Final%20-%20Flux%20Audit%20Report.pdf
