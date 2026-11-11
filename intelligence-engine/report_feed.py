#!/usr/bin/env python3
"""Cursor-based report feeder for knowledge distillation.

Lists a source repo's reports (cached once) and fetches ONE report's text at a
time, in memory — nothing persists but a tiny path-list cache. The distill
workflow uses this so Claude can walk reports one-by-one and extract lessons,
without ever storing a heavy local corpus of PDFs.

    python report_feed.py --source sherlock --count
    python report_feed.py --source sherlock --list
    python report_feed.py --source sherlock --index 0
    python report_feed.py --source sherlock --index 0 --max-chars 40000

Output is JSON on stdout. PDFs need PyMuPDF; markdown needs nothing. The report
listing is cached under storage/.feed-cache/<source>.json (just paths — KB, not
the reports themselves); pass --refresh to rebuild it.
"""
import argparse
import json
import sys
from pathlib import Path

import ingest_stream as S

try:
    import yaml
except ImportError:
    yaml = None

CACHE = Path(__file__).resolve().parent.parent / "storage" / ".feed-cache"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"


def git_sources(config: str) -> dict:
    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    return {s["name"]: s for s in cfg.get("sources", []) if s.get("type") == "git"}


def get_listing(name: str, src: dict, refresh: bool = False) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    cf = CACHE / f"{name}.json"
    if cf.exists() and not refresh:
        return json.loads(cf.read_text(encoding="utf-8"))
    owner, repo = S.owner_repo(src["repo"])
    branch = S.default_branch(owner, repo)
    paths = S.list_reports(owner, repo, branch)
    data = {"owner": owner, "repo": repo, "branch": branch,
            "base_url": src.get("base_url", ""), "paths": paths}
    cf.write_text(json.dumps(data), encoding="utf-8")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--list", action="store_true", help="print all report paths (JSON)")
    ap.add_argument("--count", action="store_true", help="print the number of reports")
    ap.add_argument("--index", type=int, help="fetch the Nth report's text (JSON)")
    ap.add_argument("--max-chars", type=int, default=45000,
                    help="truncate report text to this many chars (context budget)")
    ap.add_argument("--refresh", action="store_true", help="rebuild the listing cache")
    args = ap.parse_args()

    if yaml is None:
        print(json.dumps({"error": "pyyaml not installed"})); sys.exit(1)

    srcs = git_sources(args.config)
    if args.source not in srcs:
        print(json.dumps({"error": f"unknown git source '{args.source}'",
                          "available": list(srcs)})); sys.exit(1)

    listing = get_listing(args.source, srcs[args.source], args.refresh)
    paths = listing["paths"]

    if args.count:
        print(json.dumps({"source": args.source, "count": len(paths)})); return
    if args.list:
        print(json.dumps({"source": args.source, "count": len(paths),
                          "paths": [{"index": i, "path": p} for i, p in enumerate(paths)]},
                         indent=2)); return

    if args.index is None:
        print(json.dumps({"error": "pass --list, --count, or --index N"})); sys.exit(1)
    if not (0 <= args.index < len(paths)):
        print(json.dumps({"error": f"index out of range 0..{len(paths)-1}"})); sys.exit(1)

    path = paths[args.index]
    text = S.fetch_text(listing["owner"], listing["repo"], listing["branch"], path)
    if text is None:
        print(json.dumps({"source": args.source, "index": args.index, "path": path,
                          "error": "fetch/parse failed (PyMuPDF missing for PDF?)"}))
        sys.exit(2)
    import urllib.parse
    bu = listing["base_url"].rstrip("/")
    url = (f"{bu}/blob/{listing['branch']}/{urllib.parse.quote(path)}" if bu else "")
    truncated = len(text) > args.max_chars
    print(json.dumps({
        "source": args.source, "index": args.index, "count": len(paths),
        "path": path, "url": url, "truncated": truncated,
        "text": text[:args.max_chars],
    }))


if __name__ == "__main__":
    main()
