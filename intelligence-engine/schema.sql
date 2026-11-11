-- Audit-intelligence knowledge base (SQLite + FTS5).
-- Per-finding storage: each historical audit finding is one row, traceable to
-- its source report. Original text is preserved; nothing is lossy-summarized.

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS sources (
    id       INTEGER PRIMARY KEY,
    name     TEXT UNIQUE NOT NULL,   -- sherlock | cyfrin | code4rena | openzeppelin
    url      TEXT,
    license  TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER NOT NULL REFERENCES sources(id),
    title         TEXT,
    url           TEXT,
    local_path    TEXT,               -- preserved original (md/pdf)
    content_hash  TEXT UNIQUE,        -- skip re-ingesting unchanged reports
    ingested_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS findings (
    id             INTEGER PRIMARY KEY,
    report_id      INTEGER NOT NULL REFERENCES reports(id),
    source_name    TEXT NOT NULL,
    title          TEXT,
    body           TEXT,              -- original finding text (evidence)
    orig_severity  TEXT,              -- as written in the report
    norm_severity  TEXT,              -- critical|high|medium|low|info
    language       TEXT,              -- solidity|rust|unknown
    ecosystem      TEXT,              -- evm|solana|unknown
    category       TEXT,              -- normalized vuln category (taxonomy)
    url            TEXT,              -- back-reference to the report
    content_hash   TEXT UNIQUE
);

-- FTS5 over findings (external-content). Rebuild/maintain via triggers.
CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts USING fts5(
    title, body, category,
    content='findings', content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS findings_ai AFTER INSERT ON findings BEGIN
    INSERT INTO findings_fts(rowid, title, body, category)
    VALUES (new.id, new.title, new.body, new.category);
END;
CREATE TRIGGER IF NOT EXISTS findings_ad AFTER DELETE ON findings BEGIN
    INSERT INTO findings_fts(findings_fts, rowid, title, body, category)
    VALUES ('delete', old.id, old.title, old.body, old.category);
END;
CREATE TRIGGER IF NOT EXISTS findings_au AFTER UPDATE ON findings BEGIN
    INSERT INTO findings_fts(findings_fts, rowid, title, body, category)
    VALUES ('delete', old.id, old.title, old.body, old.category);
    INSERT INTO findings_fts(rowid, title, body, category)
    VALUES (new.id, new.title, new.body, new.category);
END;

CREATE INDEX IF NOT EXISTS idx_findings_lang ON findings(language);
CREATE INDEX IF NOT EXISTS idx_findings_cat  ON findings(category);
CREATE INDEX IF NOT EXISTS idx_findings_sev  ON findings(norm_severity);
