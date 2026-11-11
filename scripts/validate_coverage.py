#!/usr/bin/env python3
"""Validate the source-coverage ledger.

Fails (exit 1) if any in-scope file is neither examined nor explicitly excluded
with a reason. Prints a summary either way.

Usage:
    python validate_coverage.py <coverage.json>
"""
import argparse
import json
import sys
from pathlib import Path


def validate(ledger: list) -> tuple[bool, list]:
    problems = []
    for row in ledger:
        p = row.get("path", "<unknown>")
        examined = row.get("examined", False)
        excluded = row.get("excluded", False)
        if excluded and not row.get("exclusion_reason"):
            problems.append(f"{p}: excluded without a reason")
        elif not examined and not excluded:
            problems.append(f"{p}: not examined and not excluded")
    return (len(problems) == 0, problems)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    args = ap.parse_args()

    data = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("files", [])
    ok, problems = validate(rows)

    examined = sum(1 for r in rows if r.get("examined"))
    excluded = sum(1 for r in rows if r.get("excluded"))
    print(f"coverage: {len(rows)} in-scope, {examined} examined, {excluded} excluded")
    if not ok:
        print(f"INCOMPLETE — {len(problems)} issue(s):", file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        sys.exit(1)
    print("coverage complete")


if __name__ == "__main__":
    main()
