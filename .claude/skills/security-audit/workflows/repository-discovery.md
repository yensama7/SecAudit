# Workflow: repository discovery

Build the map before auditing. Output feeds `source-inventory.json` and your
mental model.

## Steps
1. Run `scripts/discover_sources.py <root>` — it walks the tree and classifies
   each `.sol`/`.rs` file as `in_scope`, `vendor`, `generated`, or `test` using
   path heuristics (see below). Read its JSON output.
2. Sanity-check the classification against any scope definition the repo
   provides: README, `scope.txt`, a contest page, `foundry.toml`/`Anchor.toml`
   paths, remappings. If the repo says a file is in scope and the heuristic said
   vendor, trust the repo — fix the inventory.
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
