#!/usr/bin/env python3
"""Validate the auditor-findings handoff artifact before stage 2 runs.

Focused structural check (not full JSON Schema — stdlib only). Enforces the
plan's handoff contract: every finding has a location + evidence, severity and
confidence use allowed values, coverage state is recorded, and the repo revision
is present. Exit 0 = valid handoff; exit 1 = do NOT proceed to intelligence.

Usage:
    python validate_handoff.py <auditor-findings.json>
"""
import argparse
import json
import sys
from pathlib import Path

SEVERITY = {"critical", "high", "medium", "low"}
CONFIDENCE = {"high", "medium", "low"}
VERIFY = {"verified", "needs_investigation"}
MIN_TEXT = 15  # evidence/root_cause must be real, not a placeholder


def validate(doc: dict) -> list:
    errs = []

    for key in ("run_id", "repository", "languages", "coverage", "findings"):
        if key not in doc:
            errs.append(f"missing top-level key: {key}")
    if errs:
        return errs  # structure too broken to continue

    repo = doc["repository"]
    if not repo.get("root"):
        errs.append("repository.root missing")
    if not repo.get("commit"):
        errs.append("repository.commit missing (use 'no-vcs' if not a git repo)")

    cov = doc["coverage"]
    if "complete" not in cov:
        errs.append("coverage.complete flag missing")
    if not isinstance(cov.get("in_scope_files"), int):
        errs.append("coverage.in_scope_files must be an integer")

    findings = doc["findings"]
    if not isinstance(findings, list):
        return errs + ["findings must be a list"]
    if len(findings) > 20:
        errs.append(f"too many findings: {len(findings)} (max 20)")

    seen_ids = set()
    for i, f in enumerate(findings):
        tag = f.get("id", f"#{i}")
        if tag in seen_ids:
            errs.append(f"{tag}: duplicate finding id")
        seen_ids.add(tag)

        if f.get("severity") not in SEVERITY:
            errs.append(f"{tag}: severity '{f.get('severity')}' not in {SEVERITY}")
        if f.get("confidence") not in CONFIDENCE:
            errs.append(f"{tag}: confidence '{f.get('confidence')}' not in {CONFIDENCE}")
        if f.get("verification_status") not in VERIFY:
            errs.append(f"{tag}: verification_status invalid")

        locs = f.get("locations") or []
        if not locs:
            errs.append(f"{tag}: no location (file:line) — every finding needs one")
        for loc in locs:
            if not loc.get("path") or "start_line" not in loc:
                errs.append(f"{tag}: incomplete location {loc}")

        for field in ("root_cause", "impact", "evidence", "remediation"):
            if len((f.get(field) or "").strip()) < MIN_TEXT:
                errs.append(f"{tag}: {field} missing or too short (needs real content)")

        fp = f.get("fingerprint") or {}
        if not fp.get("language") or not fp.get("category"):
            errs.append(f"{tag}: fingerprint needs language + category (for stage-2 retrieval)")

    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings")
    args = ap.parse_args()

    path = Path(args.findings)
    if not path.exists():
        print(f"error: {path} does not exist — stage 1 did not produce a handoff",
              file=sys.stderr)
        sys.exit(1)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"error: {path} is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    errs = validate(doc)
    if errs:
        print(f"HANDOFF INVALID — {len(errs)} problem(s). Do NOT start stage 2:",
              file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    n = len(doc["findings"])
    complete = doc["coverage"].get("complete")
    print(f"handoff valid: {n} finding(s), coverage_complete={complete}")
    if not complete:
        print("note: coverage incomplete — intelligence may run but the audit "
              "must be reported as INCOMPLETE.")


if __name__ == "__main__":
    main()
