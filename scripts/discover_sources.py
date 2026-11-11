#!/usr/bin/env python3
"""Discover and classify source files for a security audit.

Walks a repo, finds .sol/.rs files, classifies each as in_scope / vendor /
generated / test using path heuristics. The repo's own scope statement always
overrides these heuristics (the auditor reconciles that manually).

Usage:
    python discover_sources.py <repo_root> [--out source-inventory.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

LANG_BY_EXT = {".sol": "solidity", ".rs": "rust"}

VENDOR = re.compile(
    r"(^|/)(lib|node_modules|vendor|target|\.cargo|out|artifacts|cache)(/|$)"
    r"|openzeppelin|forge-std|solmate|@openzeppelin",
    re.I,
)
GENERATED = re.compile(r"\.g\.sol$|/artifacts/|/out/|\.min\.|/idl/", re.I)
TEST = re.compile(
    r"(^|/)(test|tests|script|scripts|mock|mocks)(/|$)|\.t\.sol$|test.*\.rs$|_test\.rs$",
    re.I,
)


def classify(rel_path: str) -> str:
    """Classify a repo-relative path. Order matters: vendor beats test beats scope."""
    p = rel_path.replace("\\", "/")
    if VENDOR.search(p):
        return "vendor"
    if GENERATED.search(p):
        return "generated"
    if TEST.search(p):
        return "test"
    return "in_scope"


def discover(root: Path) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in LANG_BY_EXT:
            continue
        rel = path.relative_to(root).as_posix()
        files.append(
            {
                "path": rel,
                "language": LANG_BY_EXT[path.suffix],
                "classification": classify(rel),
                "size_bytes": path.stat().st_size,
            }
        )
    langs = sorted({f["language"] for f in files if f["classification"] == "in_scope"})
    return {
        "root": str(root),
        "languages": langs,
        "counts": {
            c: sum(1 for f in files if f["classification"] == c)
            for c in ("in_scope", "vendor", "generated", "test")
        },
        "files": files,
    }


def _self_test():
    assert classify("lib/openzeppelin/ERC20.sol") == "vendor"
    assert classify("src/Vault.sol") == "in_scope"
    assert classify("test/Vault.t.sol") == "test"
    assert classify("programs/foo/src/lib.rs") == "in_scope"
    assert classify("src/vault.g.sol") == "generated"
    assert classify("node_modules/x/a.sol") == "vendor"
    print("discover_sources self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", help="repo root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return
    if not args.root:
        ap.error("root is required")

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        sys.exit(2)

    inv = discover(root)
    out = json.dumps(inv, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out}: {inv['counts']}")
    else:
        print(out)


if __name__ == "__main__":
    main()
