import os
import threading

import psycopg2
import psycopg2.extras
from psycopg2.pool import PoolError, SimpleConnectionPool

from errors import ApiError

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://hl:hl@db:5432/hl"
)

# Pool sizing. Starlette runs sync endpoints in a threadpool of 40, so at most
# 40 requests can be inside query()/execute() at once; DB work is short, so a
# pool smaller than that is pointless headroom reduction rather than a
# resource cap. Bounded at 20 for now -- IMPORTANT: this must satisfy
#   workers x POOL_MAX <= postgres max_connections (default 100)
# so when Phase 3 adds multiple uvicorn workers, lower this accordingly.
POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
POOL_MAX = int(os.environ.get("DB_POOL_MAX", "20"))
# Bounded wait. psycopg2's SimpleConnectionPool.getconn() blocks indefinitely
# and offers no timeout, and psycopg2.pool.PoolError is only reachable once
# the pool is full. A semaphore the same width as the pool gives us the two
# things we actually want: a bounded wait, and a clean 503 instead of a thread
# stuck forever or an opaque 500.
POOL_MAXWAIT = float(os.environ.get("DB_POOL_MAXWAIT", "5"))

_pool = None
_slots = threading.Semaphore(POOL_MAX)


def pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            POOL_MIN,
            POOL_MAX,
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pool


def _acquire():
    if not _slots.acquire(timeout=POOL_MAXWAIT):
        raise ApiError(
            503,
            "db_pool_exhausted",
            "The database is busy right now. Please retry shortly.",
            what=(
                f"All {POOL_MAX} pooled connections were in use for longer than "
                f"the {POOL_MAXWAIT:g}s wait limit. Nothing was written and no "
                f"transaction was started."
            ),
            fix="Wait a moment and retry the identical request.",
            next_actions=[
                "Retry after a short delay.",
                "If this persists, the database is the bottleneck: compare "
                "GET /api/perf (per-route latency) against GET /api/perf/queries "
                "(slowest statements) to see whether queries or contention is "
                "the cause.",
            ],
            headers={"Retry-After": "2"},
            extra={"pool_max": POOL_MAX, "max_wait_s": POOL_MAXWAIT},
        )
    try:
        return pool().getconn()
    except PoolError as exc:  # pragma: no cover - semaphore should prevent this
        _slots.release()
        raise ApiError(
            503,
            "db_pool_exhausted",
            "The database is busy right now. Please retry shortly.",
            what=str(exc),
            fix="Wait a moment and retry the identical request.",
            headers={"Retry-After": "2"},
        ) from exc


def query(sql, args=None, one=False):
    conn = _acquire()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall() if cur.description else []
            return (rows[0] if rows else None) if one else rows
    finally:
        pool().putconn(conn)
        _slots.release()


def execute(sql, args=None):
    conn = _acquire()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
    finally:
        pool().putconn(conn)
        _slots.release()


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
