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
