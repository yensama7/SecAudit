#!/usr/bin/env python3
"""Hybrid retrieval over the findings knowledge base.

FTS5 full-text (BM25-ranked) + metadata filters (language / category /
severity). This is the CLI fallback the audit skill uses when the MCP server
isn't connected, and the shared query layer the MCP server calls.

Usage:
    python retrieve.py "reentrancy external call before state update" \
        --lang solidity --category reentrancy --limit 8
"""
import argparse
import json
import re
import sys

import db

# Keep only alnum tokens for the FTS MATCH query; OR them so partial overlap
# still ranks. Quoting each term avoids FTS5 syntax errors from punctuation.
_TOK = re.compile(r"[A-Za-z0-9_]+")


def _fts_query(text: str) -> str:
    terms = [t for t in _TOK.findall(text or "") if len(t) > 2]
    return " OR ".join(f'"{t}"' for t in terms[:20]) or '""'


def search(conn, query: str, language=None, category=None, severity=None, limit=8):
    fts = _fts_query(query)
    where = ["findings_fts MATCH ?"]
    params = [fts]
    if language and language != "unknown":
        where.append("f.language = ?")
        params.append(language)
    if category:
        where.append("f.category = ?")
        params.append(category)
    if severity:
        where.append("f.norm_severity = ?")
        params.append(severity)
    params.append(limit)

    sql = f"""
        SELECT f.id, f.source_name, f.title, f.orig_severity, f.norm_severity,
               f.language, f.ecosystem, f.category, f.url,
               substr(f.body, 1, 300) AS snippet,
               bm25(findings_fts) AS score
        FROM findings_fts
        JOIN findings f ON f.id = findings_fts.rowid
        WHERE {" AND ".join(where)}
        ORDER BY score
        LIMIT ?
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print(f"query error: {e}", file=sys.stderr)
        return []
    return [dict(r) for r in rows]


def get_finding(conn, finding_id: int):
    r = conn.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()
    return dict(r) if r else None


def get_reference(conn, finding_id: int):
    r = conn.execute(
        """SELECT f.id, f.title, f.url, f.source_name, f.orig_severity,
                  r.title AS report_title, r.url AS report_url, r.local_path
           FROM findings f JOIN reports r ON r.id = f.report_id
           WHERE f.id = ?""",
        (finding_id,),
    ).fetchone()
    return dict(r) if r else None


def search_patterns(conn, query: str, language=None, limit=10):
    """Category-level view: which normalized vuln patterns match, with counts."""
    hits = search(conn, query, language=language, limit=50)
    agg = {}
    for h in hits:
        c = h["category"]
        agg.setdefault(c, {"category": c, "count": 0, "examples": []})
        agg[c]["count"] += 1
        if len(agg[c]["examples"]) < 3:
            agg[c]["examples"].append({"id": h["id"], "title": h["title"],
                                       "source": h["source_name"]})
    return sorted(agg.values(), key=lambda x: -x["count"])[:limit]


def related(conn, finding_id: int, limit=5):
    base = get_finding(conn, finding_id)
    if not base:
        return []
    hits = search(conn, f"{base['title']} {base['category']}",
                  language=base["language"], category=base["category"], limit=limit + 1)
    return [h for h in hits if h["id"] != finding_id][:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--category", default=None)
    ap.add_argument("--severity", default=None)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    conn = db.connect()
    hits = search(conn, args.query, args.lang, args.category, args.severity, args.limit)
    if args.json:
        print(json.dumps(hits, indent=2))
        return
    if not hits:
        print("no matches (is the knowledge base ingested? run ingest.py)")
        return
    for h in hits:
        print(f"[{h['id']}] ({h['norm_severity']}/{h['category']}/{h['source_name']}) "
              f"{h['title']}")
        print(f"     {h['snippet'].strip()[:160].replace(chr(10), ' ')}")
        print(f"     {h['url']}\n")


if __name__ == "__main__":
    main()
