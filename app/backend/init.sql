CREATE TABLE IF NOT EXISTS wallets (
    address TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS runs (
    id          SERIAL PRIMARY KEY,
    wallet      TEXT NOT NULL REFERENCES wallets(address) ON DELETE CASCADE,
    label       TEXT NOT NULL,
    tool        TEXT,
    model       TEXT,
    variant     TEXT,
    status      TEXT,
    probe       TEXT,
    duration_s  REAL,
    bytes       BIGINT,
    report_path TEXT,
    context_size INT,
    global_score INT NOT NULL DEFAULT 0,
    UNIQUE (wallet, label)
);

CREATE TABLE IF NOT EXISTS wallet_summaries (
    wallet       TEXT PRIMARY KEY REFERENCES wallets(address) ON DELETE CASCADE,
    consensus_strategy TEXT,
    key_params         TEXT,
    trade_example      TEXT,
    disagreements      JSONB,
    model_count        INT,
    strategy_report_count INT,
    no_strategy_count  INT,
    confidence         TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    generated_by       TEXT,
    generated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- one rating per run (single user); value: +1 interesting, -1 not
CREATE TABLE IF NOT EXISTS ratings (
    run_id     INT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    value      INT NOT NULL CHECK (value IN (-1, 1)),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_model_idx ON runs(model);

-- Idempotent migration: trade_example was added after the table existed.
ALTER TABLE wallet_summaries ADD COLUMN IF NOT EXISTS trade_example TEXT;

-- Idempotent migration: context_size was added after the table existed.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS context_size INT;

-- Idempotent migration: has_real_report marks runs whose strategy_report.md
-- is an actual answer (not a "NO STRATEGY — ..." flag). A run can time out
-- (exit 124) yet still have produced a complete report; the pill should
-- show DONE in that case.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS has_real_report BOOLEAN DEFAULT FALSE;

-- Follow-up Q&A conversations on a stored answer (RAG over its report).
CREATE TABLE IF NOT EXISTS conversations (
    id         SERIAL PRIMARY KEY,
    run_id     INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    model      TEXT,
    citations  JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS conversations_run_idx ON conversations(run_id);

-- Semantic index over strategy reports: report_chunks is the document store
-- (ask.py retrieves context from it) and embedding_cache keeps each text's
-- vector keyed by (sha1(text), model). Both are derived data -- safe to drop
-- and rebuild from the report files (see vector_index.py).
CREATE TABLE IF NOT EXISTS report_chunks (
    id          SERIAL PRIMARY KEY,
    run_id      INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text        TEXT NOT NULL,
    UNIQUE (run_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS report_chunks_run_idx ON report_chunks(run_id);

CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash  TEXT NOT NULL,
    model      TEXT NOT NULL,
    embedding  JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (text_hash, model)
);

-- Asynchronous agent jobs. A POST /ask returns 202 + job_id immediately and a
-- worker claims rows with FOR UPDATE SKIP LOCKED, so a request never holds a
-- server thread for the (up to 300s) lifetime of an AI CLI subprocess.
-- status: pending -> running -> done | error
CREATE TABLE IF NOT EXISTS agent_jobs (
    id          SERIAL PRIMARY KEY,
    run_id      INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    tool        TEXT NOT NULL,
    model       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','running','done','error')),
    answer      TEXT,
    citations   JSONB,
    error       TEXT,
    from_ui     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS agent_jobs_status_idx ON agent_jobs(status);
CREATE INDEX IF NOT EXISTS agent_jobs_run_idx ON agent_jobs(run_id);

-- Denormalised model score.
--
-- global_score is the sum of every rating for a run's model, across all
-- wallets. Computing it inline meant every /api/wallets/{addr}/runs call
-- re-aggregated the whole ratings x runs table (measured: the single hottest
-- query, ~70k rows per 2.3k calls). A rating is a rare human action and the
-- table is small, so we recompute all scores per statement rather than doing
-- per-row delta arithmetic.
-- Two functions on purpose: Postgres requires anything invoked by CREATE
-- TRIGGER to return `trigger`, but the recalculation is also called directly
-- for the one-off backfill. A single VOID function satisfies the second need
-- and silently breaks the first.
CREATE OR REPLACE FUNCTION runs_recalc_global_scores() RETURNS VOID AS $$
BEGIN
    UPDATE runs r SET global_score = COALESCE(s.score, 0)
    FROM (
        SELECT r2.model, SUM(COALESCE(rt.value, 0)) AS score
        FROM runs r2
        LEFT JOIN ratings rt ON rt.run_id = r2.id
        WHERE r2.model IS NOT NULL
        GROUP BY r2.model
    ) s
    WHERE r.model = s.model;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION runs_recalc_global_scores_trg() RETURNS trigger AS $$
BEGIN
    PERFORM runs_recalc_global_scores();
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ratings_recalc_global_scores ON ratings;
CREATE TRIGGER ratings_recalc_global_scores
AFTER INSERT OR UPDATE OR DELETE ON ratings
FOR EACH STATEMENT EXECUTE FUNCTION runs_recalc_global_scores_trg();
