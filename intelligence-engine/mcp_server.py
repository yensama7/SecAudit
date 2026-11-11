#!/usr/bin/env python3
"""MCP server exposing the audit-intelligence knowledge base to Claude Code.

Tools (per PLAN.md section 7):
  search_audit_findings        hybrid search over historical findings
  get_finding_details          full structured finding
  get_audit_reference          original report provenance / location
  search_vulnerability_patterns normalized vuln-pattern (category) search
  get_related_findings         findings linked to a given one

These return evidence + references only — never a security verdict. Claude does
the comparison against the live code.

Requires the `mcp` SDK (pip install mcp). If you don't want the dependency, the
audit skill falls back to retrieve.py on the CLI — same query layer.

Register in Claude Code (.mcp.json or `claude mcp add`):
    "audit-intel": { "command": "python",
                     "args": ["intelligence-engine/mcp_server.py"] }
"""
import json

import db
import retrieve

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "mcp SDK not installed. `pip install mcp`, or use retrieve.py on the CLI."
    ) from e

mcp = FastMCP("audit-intel")
_conn = db.connect()


@mcp.tool()
def search_audit_findings(query: str, language: str = "", category: str = "",
                          severity: str = "", limit: int = 8) -> str:
    """Hybrid search over historical competitive-audit findings. Returns a JSON
    list of matches (id, title, severity, category, source, url, snippet).
    Filter with language (solidity/rust), category (taxonomy slug), severity."""
    hits = retrieve.search(_conn, query, language or None, category or None,
                           severity or None, limit)
    return json.dumps(hits, indent=2)


@mcp.tool()
def get_finding_details(finding_id: int) -> str:
    """Full structured historical finding (original title + body text + metadata)."""
    return json.dumps(retrieve.get_finding(_conn, finding_id), indent=2)


@mcp.tool()
def get_audit_reference(finding_id: int) -> str:
    """Original report provenance for a finding: source, report title, URLs, path."""
    return json.dumps(retrieve.get_reference(_conn, finding_id), indent=2)


@mcp.tool()
def search_vulnerability_patterns(query: str, language: str = "", limit: int = 10) -> str:
    """Search normalized vulnerability patterns (categories) with match counts and
    example findings — for recognizing an underlying weakness class."""
    return json.dumps(retrieve.search_patterns(_conn, query, language or None, limit),
                      indent=2)


@mcp.tool()
def get_related_findings(finding_id: int, limit: int = 5) -> str:
    """Findings related to a given one (same category/language, text-similar)."""
    return json.dumps(retrieve.related(_conn, finding_id, limit), indent=2)


if __name__ == "__main__":
    mcp.run()
