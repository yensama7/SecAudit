# Security Audit Intelligence System

A terminal-first competitive-auditing assistant that runs inside **Claude Code**.
One command runs two automatic stages:

1. **Security Auditor** — inspects a Solidity/Rust repo, examines every in-scope
   file, and produces evidence-backed findings.
2. **Audit Intelligence** — cross-checks each finding against a **distilled
   knowledge library**: compact "what to look for / how it's fixed" lessons
   extracted from historical competitive audits (Sherlock, Cyfrin, …), then
   judges whether the real code exhibits — or already remedies — each pattern.

New to auditing? The methodology under
`.claude/skills/security-audit/` is written to be read — taxonomies, checklists,
worked vulnerability patterns, and a severity model. Start there.

## Setup (once)

```bash
pip install -r intelligence-engine/requirements.txt   # pyyaml, pypdf
```

## Build the knowledge (distillation)

The "audit intelligence" is a **distilled knowledge library** — compact "what to
look for / how it's fixed" lessons extracted from historical audits — not a bulk
copy of the reports. Build it convergently, one source at a time:

```bash
python distill.py --source sherlock                     # do this first
python distill.py --source cyfrin                        # then this
python distill.py --source sherlock --max-tokens 50000   # cap a run at ~50k tokens
```

> **Run `distill.py` (and `audit.py`) from your own terminal, not from inside a
> Claude Code session.** They launch a *second* headless Claude Code session via
> `claude-work`; nested launches inherit a PATH where the npm `claude` shim is
> broken (and share this session's quota). A plain terminal where `claude-work`
> works is the supported way to run them.

`--max-tokens N` meters the nested session's cumulative tokens (via streaming
JSON) and stops at the budget. Because state is checkpointed per report, a capped
run is fully resumable — run the same command again to continue.

`distill.py` drives Claude Code to read reports **one at a time, streamed and
parsed in memory** (via `intelligence-engine/report_feed.py`), extract each
distinct lesson, and merge it into
`.claude/skills/security-audit/knowledge/<category>.md` — stopping once a source
stops teaching anything new. **Nothing heavy is stored**: no clones, no PDFs on
disk — only the tiny lessons plus a KB-sized path-list cache. Runs resume from
the saved cursor in `knowledge/distill-state.json`, so you can stop/restart.

Interactively, you can instead open the repo in Claude Code and say "distill the
sherlock knowledge" (see `workflows/distill-knowledge.md`).

Verify the tooling with no deps/network:

```bash
python scripts/discover_sources.py --self-test
python intelligence-engine/ingest.py --self-test
python intelligence-engine/report_feed.py --source sherlock --count   # needs network
```

## Running an audit

### From the CLI (one command, any repo)

```bash
python audit.py https://github.com/org/repo          # GitHub URL
python audit.py ./path/to/repo                        # local folder
python audit.py ./repo --output ./audits --model claude-opus-4-8
python audit.py ./repo --dry-run                      # print the claude command, don't run
```

`audit.py` clones the URL (or takes the folder), then drives **Claude Code in
headless mode** against it and collects `.security-audit/final-report.md`. It
does **not** call the Anthropic API — Claude Code is the harness, so the skill
and the `audit-intel` MCP server are reused as-is. Auth is your Claude Code
login; no API key.

If your `claude` launcher isn't on `PATH` (or the npm shim is broken), point the
CLI at it: `set SECAUDIT_CLAUDE_BIN=C:\path\to\claude.cmd` (or `--claude-bin`).
Run `--dry-run` first to inspect the exact command.

### Interactively

Open a target repo in Claude Code and invoke the skill:

```
/security-audit        (or: "audit this repo for vulnerabilities")
```

Either way Claude will: discover sources → examine every in-scope file (tracked
in a coverage ledger) → write validated findings → auto-run intelligence
retrieval → produce `.security-audit/final-report.md`. You don't switch stages
manually.

## Manual retrieval (no Claude needed)

```bash
python intelligence-engine/retrieve.py \
  "reentrancy external call before state update" --lang solidity --category reentrancy
```

## Layout

```
audit.py                         CLI: audit a GitHub URL / local folder (headless Claude Code)
distill.py                       CLI: build the distilled-knowledge library (headless, convergent)
.claude/skills/security-audit/   audit methodology + knowledge/ (distilled lessons) + workflows
scripts/                         discovery, coverage + handoff validation, report builder
intelligence-engine/             report_feed.py (stream reports in memory), ingest*/retrieve (legacy DB)
config/                          sources.yaml (report sources), languages.yaml
storage/.feed-cache/             tiny per-source path lists (gitignored); no reports on disk
```

## Design notes

- **Distilled knowledge, not a corpus.** The intelligence is "what to look for /
  how it's fixed" lessons in `.claude/skills/security-audit/knowledge/`, built by
  reading reports **in memory** and discarding them. Persistent footprint is a
  few KB of lessons + a path-list cache — no multi-GB clones, no PDFs on disk.
- **Claude is the brain.** Both the audit and the distillation run as headless
  Claude Code (your login; no Anthropic API key). The skill + workflows are the
  methodology; the knowledge library is the accumulated experience.
- **Similarity is never confirmation.** A matching pattern guides investigation;
  severity always comes from the current code's impact.
- **Coverage is a ledger.** An audit is never "complete" while an in-scope file
  is unexamined — the report says so when it isn't.
- **Legacy retrieval DB.** The SQLite+FTS5 raw-findings path (`ingest.py`,
  `ingest_stream.py`, `retrieve.py`, `mcp_server.py`) still works and is an
  optional supplement, but the distilled library is primary.

See `PLAN.md` for the full design and `DEVIATIONS.md` for where this v1
intentionally simplifies the plan.
