# Initialization / upgradeability — what to look for

### Public initializer with no once-guard → anyone re-initializes (proxy/beacon takeover)
- **Look for:** an `initialize*` function (especially `initializeBeacon`, proxy or
  beacon setup) with `public`/`external` visibility and **no** `initializer`
  modifier / no "already initialized" check. Common when a team swaps a
  constructor for an init function to make the contract Create2/factory-friendly.
  Anyone can call it again to point the proxy/beacon at a **malicious
  implementation** and subvert every call routed through it.
- **Root cause:** moving setup out of the constructor without re-adding the
  "runs exactly once" guarantee the constructor gave for free.
- **How it's fixed:** apply OpenZeppelin's `initializer` (or `reinitializer`)
  modifier so init can run only once during proxy creation; and/or
  `_disableInitializers()` in the implementation's constructor so the logic
  contract can't be initialized directly.
- **Languages:** solidity
- **Typical severity:** high–critical (full protocol takeover via swapped implementation)
- **Seen in:** https://github.com/sherlock-protocol/sherlock-reports/blob/main/audits/2022.06.30%20-%20Final%20-%20Hook%20Audit%20Report.pdf
