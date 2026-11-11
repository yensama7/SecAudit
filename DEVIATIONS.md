# Deviations from PLAN.md (v1)

Intentional simplifications in this first version. Each notes when to upgrade.

## v1.1 — distilled knowledge replaces bulk ingestion (primary path)

The PLAN's Audit Intelligence stage stored every historical finding verbatim and
retrieved by similarity. v1.1 pivots: instead of importing heavy reports, we
**distil** each report into compact "what to look for / how it's fixed" lessons
(`.claude/skills/security-audit/knowledge/<category>.md`), built convergently by
`distill.py` (headless Claude Code) reading reports **streamed and parsed in
memory** (`report_feed.py`). Why: the lessons are what actually instruct an
audit; raw-finding similarity is noisy and heavy. Footprint drops from several GB
of clones to a few KB of lessons. The SQLite+FTS5 raw-findings path (`ingest.py`,
`ingest_stream.py`, `retrieve.py`, `mcp_server.py`) is kept as an optional
supplement. Also: `audit.py` is a one-command CLI (GitHub URL / local folder)
that drives the audit via headless Claude Code — no Anthropic API key.

| Plan says | v1 does | Add when |
|---|---|---|
| Postgres + pgvector + MinIO + FastAPI + embedding server (Docker) | SQLite + FTS5, single file, no services. Claude is the semantic reranker. | Corpus outgrows FTS relevance, or you need concurrent multi-user access. |
| pgvector semantic embeddings | FTS5 BM25 + Claude's judgement over snippets | Keyword recall proves insufficient on real queries. |
| MinIO/S3 object storage of originals | Original md/pdf kept on disk under `storage/reports/` | You need durable/shared blob storage. |
| FastAPI service layer | Direct Python functions + MCP stdio server | A non-Claude client (web dashboard) needs HTTP. |
| Full JSON-Schema validation lib | Focused stdlib validator (`validate_handoff.py`) checking the contract's real constraints | Schema grows complex enough to warrant `jsonschema`. |
| Scrapers for all 4 sources | Working git collectors (Sherlock, Cyfrin) + URL-list collectors (C4, OZ) needing report URLs | You curate C4/OZ report URLs, or build their site scrapers. |
| Embedding model/version per finding, reranker | Not stored; BM25 only | You introduce embeddings. |
| Trail of Bits skill reuse | Not vendored yet; methodology written fresh | You pull specific ToB skills (preserve attribution/license). |

Unchanged from the plan on purpose (non-negotiables): two automatic stages from
one invocation, separation of methodology vs knowledge, recorded full-source
coverage, evidence-before-judgement, similarity≠confirmation, preserved
provenance, validated handoff, no forced 20 findings.
