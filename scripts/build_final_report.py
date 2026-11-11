#!/usr/bin/env python3
"""Assemble final-report.md from the stage-1/stage-2 artifacts.

Merges auditor-findings.json (direct analysis) with intelligence-results.json
(historical comparison) into a Markdown report. Claude then fills the executive
summary / verification prose on top of this scaffold.

Usage:
    python build_final_report.py --dir .security-audit
"""
import argparse
import datetime
import json
from pathlib import Path

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def fmt_locations(locs):
    return ", ".join(f"{l['path']}:{l['start_line']}-{l.get('end_line', l['start_line'])}"
                     for l in locs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".security-audit")
    args = ap.parse_args()
    d = Path(args.dir)

    findings_doc = load(d / "auditor-findings.json", {})
    intel = load(d / "intelligence-results.json", {})
    findings = findings_doc.get("findings", [])

    # index intelligence by finding id
    intel_by_id = {r["finding_id"]: r for r in intel.get("results", intel if isinstance(intel, list) else [])} \
        if intel else {}

    repo = findings_doc.get("repository", {})
    cov = findings_doc.get("coverage", {})
    counts = {s: sum(1 for f in findings if f.get("severity") == s)
              for s in SEV_ORDER}

    findings_sorted = sorted(findings, key=lambda f: SEV_ORDER.get(f.get("severity"), 9))

    complete = cov.get("complete", False)
    lines = []
    w = lines.append
    w(f"# Security Audit Report — {repo.get('name', repo.get('root', 'repo'))}\n")
    w(f"- **Repository:** {repo.get('root', '?')}")
    w(f"- **Revision:** {repo.get('commit', '?')}")
    w(f"- **Languages / frameworks:** {', '.join(findings_doc.get('languages', []))} / "
      f"{', '.join(findings_doc.get('frameworks', []))}")
    w(f"- **Date:** {datetime.date.today().isoformat()}")
    w(f"- **Coverage:** {cov.get('examined_files', '?')}/{cov.get('in_scope_files', '?')} "
      f"in-scope files — {'COMPLETE' if complete else 'INCOMPLETE'}\n")
    if not complete:
        w("> ⚠️ **This audit is INCOMPLETE.** Some in-scope files were not fully "
          "examined (see coverage). Findings below are valid but absence of a "
          "finding is not assurance.\n")

    w("## Severity summary\n")
    w("| Severity | Count |")
    w("|----------|-------|")
    for s in SEV_ORDER:
        w(f"| {s.capitalize()} | {counts[s]} |")
    w("")

    excluded = cov.get("excluded", [])
    if excluded:
        w("## Excluded files\n")
        for ex in excluded:
            w(f"- `{ex.get('path')}` — {ex.get('reason')}")
        w("")

    w("## Findings\n")
    if not findings_sorted:
        w("_No substantiated findings._\n")
    for f in findings_sorted:
        fid = f.get("id", "?")
        w(f"### {fid} — {f.get('title', '')}\n")
        w(f"**Severity:** {f.get('severity')}  |  **Confidence:** {f.get('confidence')}\n")
        w(f"- **Location(s):** {fmt_locations(f.get('locations', []))}")
        w(f"- **Root cause:** {f.get('root_cause', '')}")
        w(f"- **Reachability:** {f.get('reachability', '')}")
        w(f"- **Impact:** {f.get('impact', '')}")
        if f.get("trigger"):
            w(f"- **Trigger:** {f.get('trigger')}")
        w(f"\n**Evidence (this repo):**\n\n```\n{f.get('evidence', '')}\n```\n")
        w(f"**Remediation:** {f.get('remediation', '')}\n")

        ir = intel_by_id.get(fid)
        if ir and ir.get("matches"):
            w("**Historical comparison:**\n")
            for m in ir["matches"]:
                w(f"- [{m.get('verdict', '?')}] {m.get('source', '')} — "
                  f"{m.get('title', '')} (orig: {m.get('orig_severity', '?')}) "
                  f"{m.get('url', '')}")
                if m.get("reasoning"):
                    w(f"  - {m['reasoning']}")
            w("")
        else:
            w("**Historical comparison:** no relevant historical match "
              "(absence of a match is not a safety proof).\n")
        w("---\n")

    uq = findings_doc.get("unresolved_questions", [])
    if uq:
        w("## Unresolved questions\n")
        for q in uq:
            w(f"- {q}")
        w("")

    w("## Methodology note\n")
    w("Direct findings were discovered by examining this repository. Historical "
      "references guided investigation only — a match never establishes a "
      "vulnerability by itself, and severity reflects this code's impact.\n")

    out = d / "final-report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({len(findings_sorted)} findings, complete={complete})")


if __name__ == "__main__":
    main()
