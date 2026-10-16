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
