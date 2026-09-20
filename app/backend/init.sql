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
    UNIQUE (wallet, label)
);

-- one rating per run (single user); value: +1 interesting, -1 not
CREATE TABLE IF NOT EXISTS ratings (
    run_id     INT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    value      INT NOT NULL CHECK (value IN (-1, 1)),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_model_idx ON runs(model);
