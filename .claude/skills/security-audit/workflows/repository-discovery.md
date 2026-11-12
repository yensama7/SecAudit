# Workflow: repository discovery

Build the map before auditing. Output feeds `source-inventory.json` and your
mental model.

## Steps
1. Run `scripts/discover_sources.py <root>` — it walks the tree and classifies
   each `.sol`/`.rs` file as `in_scope`, `vendor`, `generated`, or `test` using
   path heuristics (see below). Read its JSON output.
2. **Read `scope.md` at the repo root first** (if it exists). This is the
   user-supplied brief and it overrides all heuristics:
   - **Product description** → understand what invariants matter and what the
     protocol's intended behaviour is; use this to sharpen what counts as a bug.
   - **In scope / Out of scope** → override the inventory: add any file the user
     listed as in scope that the heuristic missed; mark any file listed as out of
     scope as `excluded` even if the heuristic said `in_scope`.
   - **Trusted roles / assumptions** → do not raise findings that require a
     compromised or malicious instance of these roles.
   - **Known / intentional behaviors** → skip these; do not raise them as findings.
   - **Out-of-scope bug classes** → skip these entire categories.
   Then sanity-check against any other scope definition the repo provides: README,
   `scope.txt`, a contest page, `foundry.toml`/`Anchor.toml` paths, remappings.
   The user's `scope.md` takes precedence over all of these.
3. Detect the language(s) and framework: Foundry/Hardhat (Solidity),
   Anchor/native (Solana Rust). Note the compiler version and remappings.
4. For the in-scope set, build the relationship map:
   - **Entry points**: `external`/`public` functions; Solana instruction handlers.
   - **Privileged ops**: owner/admin/role-gated functions; authority-gated
     instructions.
   - **Trust boundaries**: external calls, CPIs, oracle reads, token transfers,
     user-supplied addresses/accounts.
   - **Money flows**: every path that moves ETH/tokens/lamports.
   - **Cross-file links**: inheritance, imports, interfaces, libraries.
5. Record exclusions WITH reasons in the inventory. Large/unfamiliar is NOT a
   reason to exclude — only out-of-scope (vendor/test/generated, or explicitly
   out per the repo) is.

## Scope heuristics (what discover_sources.py uses)
- vendor: paths containing `lib/`, `node_modules/`, `vendor/`,
  `openzeppelin`, `forge-std`, `.cargo`, `target/`.
- generated: `*.g.sol`, build output, `artifacts/`, `out/`, IDL output.
- test: `test/`, `tests/`, `*.t.sol`, `*test*.rs`, `mock`, `script/`.
- in_scope: everything else under `src/`, `contracts/`, `programs/`.

These are defaults; the repo's own scope statement wins.
