#!/usr/bin/env python3
"""Storage-light streaming ingestion.

Instead of cloning multi-GB report repos (which also hit NTFS illegal-filename
errors on Windows and keep resetting on flaky links), this lists a repo's
reports via the GitHub tree API, downloads each report one at a time, parses it
*in memory*, extracts findings into knowledge.db, and discards the bytes.

Result: nothing persists on disk except the (small) knowledge.db. Works on
Windows and Linux/WSL identically — the colon-named PDFs are never written to
disk. Transfers are many small raw-file GETs, not one giant pack.

Usage:
    python ingest_stream.py --source sherlock     # one source
    python ingest_stream.py --source cyfrin
    python ingest_stream.py                        # all git sources in config
    python ingest_stream.py --source sherlock --limit 25   # quick sample

Requires PyMuPDF for PDF sources (pip install PyMuPDF). Markdown needs nothing.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import db
import ingest  # extract_findings + store_report

try:
    import yaml
except ImportError:
    yaml = None

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
SKIP_NAMES = {"readme.md", "contributing.md", "license.md", "security.md",
              "code_of_conduct.md"}


def _get(url: str, accept: str = "application/vnd.github+json", timeout: int = 60):
    req = urllib.request.Request(url, headers={
        "User-Agent": "secaudit-ingest",
        "Accept": accept,
    })
    return urllib.request.urlopen(req, timeout=timeout).read()


def owner_repo(repo_url: str) -> tuple[str, str]:
    path = urllib.parse.urlparse(repo_url).path.strip("/")
    path = path.removesuffix(".git")
    owner, repo = path.split("/")[:2]
    return owner, repo


def default_branch(owner: str, repo: str) -> str:
    try:
        info = json.loads(_get(f"{API}/repos/{owner}/{repo}"))
        return info.get("default_branch", "main")
    except Exception:
        return "main"


def list_reports(owner: str, repo: str, branch: str) -> list[str]:
    data = json.loads(_get(f"{API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"))
    if data.get("truncated"):
        print(f"  warning: tree for {owner}/{repo} is truncated; some reports "
              "may be missed (repo exceeds the API's single-response limit).",
              file=sys.stderr)
    paths = []
    for t in data.get("tree", []):
        if t.get("type") != "blob":
            continue
        p = t["path"]
        low = p.lower()
        if not (low.endswith(".md") or low.endswith(".pdf")):
            continue
        if Path(p).name.lower() in SKIP_NAMES:
            continue
        paths.append(p)
    return paths


def fetch_text(owner: str, repo: str, branch: str, path: str) -> str | None:
    quoted = urllib.parse.quote(path)
    raw = _get(f"{RAW}/{owner}/{repo}/{branch}/{quoted}", accept="*/*")
    if path.lower().endswith(".md"):
        return raw.decode("utf-8", "ignore")
    return parse_pdf_bytes(raw, path)


def parse_pdf_bytes(raw: bytes, path: str = "") -> str | None:
    """Extract text from PDF bytes in memory. Prefer PyMuPDF (fitz); fall back to
    pypdf (pure-Python, tiny — installs where PyMuPDF can't). Never touches disk."""
    try:
        import fitz  # PyMuPDF, preferred
        try:
            doc = fitz.open(stream=raw, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            print(f"  skip {path}: PDF parse failed ({e})", file=sys.stderr)
            return None
    except ImportError:
        pass
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except ImportError:
        print("  skip PDF: install PyMuPDF or pypdf (pip install pypdf)", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  skip {path}: PDF parse failed ({e})", file=sys.stderr)
        return None


def ingest_source(conn, name: str, repo_url: str, base_url: str,
                  limit: int | None) -> int:
    owner, repo = owner_repo(repo_url)
    branch = default_branch(owner, repo)
    print(f"[{name}] {owner}/{repo}@{branch} — listing reports...")
    paths = list_reports(owner, repo, branch)
    if limit:
        paths = paths[:limit]
    print(f"[{name}] {len(paths)} report files to stream")
    total = 0
    for i, path in enumerate(paths, 1):
        text = fetch_text(owner, repo, branch, path)
        if not text:
            continue
        blob_url = f"{base_url.rstrip('/')}/blob/{branch}/{urllib.parse.quote(path)}" \
            if base_url else f"{RAW}/{owner}/{repo}/{branch}/{urllib.parse.quote(path)}"
        n = ingest.store_report(conn, name, Path(path).stem, blob_url, text)
        total += n
        if i % 10 == 0 or n:
            print(f"  [{i}/{len(paths)}] {Path(path).name[:60]} -> +{n} "
                  f"(running total {total})")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent
                                            / "config" / "sources.yaml"))
    ap.add_argument("--source", default=None, help="only this source name")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap reports per source (quick sample)")
    args = ap.parse_args()

    if yaml is None:
        print("error: pyyaml not installed (pip install pyyaml)", file=sys.stderr)
        sys.exit(1)

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    conn = db.connect()
    grand = 0
    for src in cfg.get("sources", []):
        if src.get("type") != "git":
            continue  # url-type sources: use ingest.py
        name = src["name"]
        if args.source and name != args.source:
            continue
        try:
            grand += ingest_source(conn, name, src["repo"],
                                    src.get("base_url", ""), args.limit)
        except Exception as e:
            print(f"[{name}] failed: {e}", file=sys.stderr)

    counts = conn.execute(
        "SELECT source_name, count(*) c FROM findings GROUP BY source_name"
    ).fetchall()
    print(f"\ningested {grand} new findings. totals:")
    for r in counts:
        print(f"  {r['source_name']}: {r['c']}")


if __name__ == "__main__":
    main()
