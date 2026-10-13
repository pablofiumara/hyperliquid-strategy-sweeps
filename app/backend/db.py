import os

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://hl:hl@db:5432/hl"
)

_pool = None


def pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            1, 10, DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
        )
    return _pool


def query(sql, args=None, one=False):
    conn = pool().getconn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall() if cur.description else []
            return (rows[0] if rows else None) if one else rows
    finally:
        pool().putconn(conn)


def execute(sql, args=None):
    conn = pool().getconn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
    finally:
        pool().putconn(conn)


def ensure_conversations_table() -> None:
    execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id          SERIAL PRIMARY KEY,
            run_id      INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            question    TEXT NOT NULL,
            answer      TEXT NOT NULL,
            model       TEXT,
            citations   JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    execute(
        "CREATE INDEX IF NOT EXISTS conversations_run_idx ON conversations(run_id)"
    )


def list_conversations(run_id: int):
    return query(
        "SELECT id, question, answer, model, citations, created_at "
        "FROM conversations WHERE run_id = %s ORDER BY created_at",
        (run_id,),
    )


def add_conversation(run_id: int, question: str, answer: str, model: str | None, citations) -> None:
    import json as _json
    execute(
        "INSERT INTO conversations (run_id, question, answer, model, citations) VALUES (%s,%s,%s,%s,%s)",
        (run_id, question, answer, model, _json.dumps(citations or [])),
    )


def get_summary(wallet: str):
    return query(
        "SELECT * FROM wallet_summaries WHERE wallet = %s", (wallet,), one=True
    )


def save_summary(data: dict) -> None:
    import json as _json

    execute(
        """
        INSERT INTO wallet_summaries
            (wallet, consensus_strategy, key_params, trade_example, disagreements,
             model_count, strategy_report_count, no_strategy_count,
             confidence, generated_by, generated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(NULLIF(%s,'')::timestamptz, now()))
        ON CONFLICT (wallet) DO UPDATE SET
            consensus_strategy    = EXCLUDED.consensus_strategy,
            key_params            = EXCLUDED.key_params,
            trade_example         = EXCLUDED.trade_example,
            disagreements         = EXCLUDED.disagreements,
            model_count           = EXCLUDED.model_count,
            strategy_report_count = EXCLUDED.strategy_report_count,
            no_strategy_count     = EXCLUDED.no_strategy_count,
            confidence            = EXCLUDED.confidence,
            generated_by          = EXCLUDED.generated_by,
            generated_at          = EXCLUDED.generated_at
        """,
        (
            data.get("wallet"),
            data.get("consensus_strategy", ""),
            data.get("key_params", ""),
            data.get("trade_example", ""),
            _json.dumps(data.get("disagreements", [])),
            data.get("model_count", 0),
            data.get("strategy_report_count", 0),
            data.get("no_strategy_count", 0),
            data.get("confidence", "low"),
            data.get("generated_by", ""),
            data.get("generated_at", ""),
        ),
    )
