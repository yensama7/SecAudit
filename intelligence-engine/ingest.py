#!/usr/bin/env python3
"""Ingest historical audit reports into the knowledge base.

Sources (config/sources.yaml):
  - git repos (Sherlock, Cyfrin): cloned/pulled, then every .md/.pdf report is
    parsed into individual findings.
  - url lists (Code4rena, OpenZeppelin): markdown report URLs fetched directly.

Extraction is heuristic: competitive-audit reports label findings with ids like
[H-01] / M-1 / C-02, grouped under severity sections. We split on those and keep
the original text verbatim. Incremental: unchanged reports (by content hash) and
duplicate findings are skipped.

Usage:
    python ingest.py --config ../config/sources.yaml          # all sources
    python ingest.py --source sherlock                        # one source
    python ingest.py --path ./storage/reports/some.md         # a single file
"""
import argparse
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import db

try:
    import yaml
except ImportError:
    yaml = None

# Where source repos/reports are cloned/fetched. Override with SECAUDIT_STORAGE —
# required on Windows for the PDF corpora (Sherlock/Cyfrin), whose report
# filenames contain characters NTFS rejects (e.g. ":"). Point it at a POSIX
# filesystem (e.g. run under WSL with SECAUDIT_STORAGE=~/secaudit-reports); the
# knowledge.db still lives next to this script, so a WSL run writes the shared DB.
STORAGE = Path(os.environ.get("SECAUDIT_STORAGE")
               or Path(__file__).resolve().parent.parent / "storage" / "reports")

# A finding header: optional markdown hashes, then an id like [H-01] / M-1 / C02,
# then a separator. Capture the severity letter.
FINDING_RE = re.compile(
    r"^\s*#{0,5}\s*\[?\s*([CHMLIG])\s*-?\s*0*(\d+)\s*\]?\s*[:.)\-–—\s]+\s*(\S.*)$",
    re.I,
)
# A severity section heading (resets the "current severity" for id-less findings).
SECTION_RE = re.compile(
    r"^\s*#{1,4}\s*(critical|high|medium|low|informational|info|gas|qa)\b",
    re.I,
)
SEV_LETTER = {"c": "critical", "h": "high", "m": "medium", "l": "low",
              "i": "info", "g": "info"}
MAX_BODY = 8000


def extract_findings(text: str):
    """Yield {title, orig_severity, body} dicts from report text (md or pdf-text)."""
    lines = text.splitlines()
    out = []
    cur = None
    section_sev = None
    for line in lines:
        m = FINDING_RE.match(line)
        if m:
            if cur:
                out.append(cur)
            letter = m.group(1).lower()
            cur = {
                "title": m.group(3).strip() or f"{letter.upper()}-{m.group(2)}",
                "orig_severity": SEV_LETTER.get(letter, section_sev or "unknown"),
                "body_lines": [line],
            }
            continue
        sec = SECTION_RE.match(line)
        if sec:
            section_sev = db.norm_severity(sec.group(1))
            if cur:  # a new severity section ends the current finding
                out.append(cur)
                cur = None
            continue
        if cur:
            cur["body_lines"].append(line)

    if cur:
        out.append(cur)

    for f in out:
        body = "\n".join(f.pop("body_lines")).strip()[:MAX_BODY]
        f["body"] = body
        # reconcile severity from section if the id letter was ambiguous
        if f["orig_severity"] in ("unknown", None):
            f["orig_severity"] = section_sev or "unknown"
    # drop empties / noise
    return [f for f in out if len(f["body"]) > 40]


def read_report_text(path: Path) -> str | None:
    if path.suffix.lower() == ".md":
        return path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print(f"  skip {path.name}: install pymupdf for PDF support", file=sys.stderr)
            return None
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    return None


def store_report(conn, source_name: str, title: str, url: str, text: str,
                 local_path: str = "") -> int:
    """Hash-check, then persist a report's extracted findings. Shared by the
    on-disk (ingest_report) and streaming (ingest_stream.py) paths. Only the
    extracted finding text is stored — not the original document — so the DB
    stays small. Provenance lives in `url`."""
    if not text:
        return 0
    h = db.sha(text)
    if conn.execute("SELECT id FROM reports WHERE content_hash=?", (h,)).fetchone():
        return 0  # unchanged, already ingested

    sid = conn.execute("SELECT id FROM sources WHERE name=?", (source_name,)).fetchone()
    if not sid:
        conn.execute("INSERT INTO sources(name) VALUES (?)", (source_name,))
        sid = conn.execute("SELECT id FROM sources WHERE name=?", (source_name,)).fetchone()
    source_id = sid[0]

    rc = conn.execute(
        "INSERT INTO reports(source_id, title, url, local_path, content_hash) "
        "VALUES (?,?,?,?,?)",
        (source_id, title, url, local_path, h),
    )
    report_id = rc.lastrowid

    n = 0
    for f in extract_findings(text):
        lang, eco = db.detect_lang_ecosystem(f["body"] + " " + text[:500])
        cat = db.categorize(f["title"], f["body"])
        fh = db.sha(f["title"] + f["body"])
        try:
            conn.execute(
                "INSERT INTO findings(report_id, source_name, title, body, "
                "orig_severity, norm_severity, language, ecosystem, category, url, content_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (report_id, source_name, f["title"], f["body"], f["orig_severity"],
                 db.norm_severity(f["orig_severity"]), lang, eco, cat, url, fh),
            )
            n += 1
        except Exception:
            pass  # duplicate finding (unique content_hash)
    conn.commit()
    return n


def ingest_report(conn, source_name: str, path: Path, url: str) -> int:
    text = read_report_text(path)
    if not text:
        return 0
    return store_report(conn, source_name, path.stem, url, text, str(path))


def ingest_dir(conn, source_name: str, root: Path, base_url: str = "") -> int:
    total = 0
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() in (".md", ".pdf") and path.is_file():
            if path.name.lower() in ("readme.md", "contributing.md", "license.md"):
                continue
            url = base_url or f"file://{path}"
            total += ingest_report(conn, source_name, path, url)
    return total


def clone_or_pull(repo_url: str, dest: Path):
    if (dest / ".git").exists():
        print(f"  pull {dest.name}")
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=False)
    else:
        print(f"  clone {repo_url} -> {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(dest)], check=True)


def ingest_url(conn, source_name: str, url: str) -> int:
    """Fetch a single markdown report by URL (for C4/OZ-style web sources)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "secaudit-ingest"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  skip {url}: {e}", file=sys.stderr)
        return 0
    tmp = STORAGE / source_name / (db.sha(url)[:16] + ".md")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding="utf-8")
    return ingest_report(conn, source_name, tmp, url)


def run_config(conn, cfg: dict, only: str | None):
    total = 0
    for src in cfg.get("sources", []):
        name = src["name"]
        if only and name != only:
            continue
        print(f"[{name}] {src.get('type')}")
        if src.get("type") == "git":
            dest = STORAGE / name
            try:
                clone_or_pull(src["repo"], dest)
            except Exception as e:
                print(f"  clone failed: {e}", file=sys.stderr)
                continue
            total += ingest_dir(conn, name, dest, src.get("base_url", ""))
        elif src.get("type") == "urls":
            for url in src.get("urls", []):
                total += ingest_url(conn, name, url)
        else:
            print(f"  unknown type {src.get('type')}, skipping", file=sys.stderr)
    return total


def _self_test():
    sample = """
# High Risk Findings

## [H-01] Reentrancy in withdraw allows draining the vault
The `withdraw` function sends ETH before updating `balances`, enabling a
re-entrant call to drain funds. No nonReentrant guard is present.

## [H-02] Missing access control on setFeeRecipient
Anyone can call setFeeRecipient because it lacks onlyOwner.

# Medium Risk Findings

## [M-01] Rounding favors the user in share conversion
Precision loss lets an attacker skim value over repeated deposits.
"""
    fs = extract_findings(sample)
    assert len(fs) == 3, fs
    assert fs[0]["orig_severity"] == "high"
    assert "reentran" in fs[0]["title"].lower()
    assert fs[2]["orig_severity"] == "medium"
    assert db.categorize(fs[0]["title"], fs[0]["body"]) == "reentrancy"
    print("ingest self-test ok:", [f["orig_severity"] for f in fs])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent
                                            / "config" / "sources.yaml"))
    ap.add_argument("--source", default=None, help="only this source name")
    ap.add_argument("--path", default=None, help="ingest a single local file")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    conn = db.connect()

    if args.path:
        p = Path(args.path)
        n = ingest_report(conn, p.parent.name or "local", p, f"file://{p}")
        print(f"ingested {n} findings from {p}")
        return

    if yaml is None:
        print("error: pyyaml not installed (pip install pyyaml)", file=sys.stderr)
        sys.exit(1)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    total = run_config(conn, cfg, args.source)
    counts = conn.execute(
        "SELECT source_name, count(*) c FROM findings GROUP BY source_name"
    ).fetchall()
    print(f"\ningested {total} new findings. totals:")
    for r in counts:
        print(f"  {r['source_name']}: {r['c']}")


if __name__ == "__main__":
    main()
