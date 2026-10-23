"""Durable job queue for AI agent calls, backed by Postgres.

Why a queue at all: an agent ask runs a CLI subprocess that can live for 300
seconds. Before this, POST /ask held a Starlette thread for that entire time,
and because the threadpool only has 40 tokens, a handful of concurrent asks
starved every other request (see docs/BASELINE.md). Here the HTTP request only
records intent and returns 202; the work happens outside the request's
lifetime, so thread occupancy is decoupled from agent duration.

Why Postgres and not Redis: one fewer service to run, the job rows double as a
durable audit trail, and FOR UPDATE SKIP LOCKED gives us safe concurrent
claiming for free across any number of worker processes. It is more than fast
enough for the rate an AI CLI can actually produce (seconds, not microseconds).

State machine:

    pending --claim--> running --complete--> done
                            \\------fail-----> error

A job left in `running` past AGENT_JOB_TIMEOUT_S is considered abandoned
(the worker died or the box was restarted) and is reaped back to `error` so a
client polling it never hangs forever.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import db


class JobCancelled(Exception):
    """Raised when an agent job is cancelled while it is running."""

# If a job has been `running` longer than this, the worker is presumed dead.
AGENT_JOB_TIMEOUT_S = int(os.environ.get("AGENT_JOB_TIMEOUT_S", "360"))

# Backpressure. A worker slot can be busy for up to AGENT_JOB_TIMEOUT_S, so an
# unbounded queue just converts "server is slow" into "reply arrives in three
# hours". Past this depth we refuse new work with a structured 429 instead.
MAX_QUEUE_DEPTH = int(os.environ.get("MAX_QUEUE_DEPTH", "50"))


def ensure_agent_jobs_table() -> None:
    """Runtime migration.

    init.sql only runs on first database creation, and this deployment has an
    existing volume, so the DDL must also be applied idempotently at startup.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_jobs (
            id          SERIAL PRIMARY KEY,
            run_id      INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            question    TEXT NOT NULL,
            tool        TEXT NOT NULL,
            model       TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','done','error','cancelled')),
            answer      TEXT,
            citations   JSONB,
            error       TEXT,
            from_ui     BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at  TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS agent_jobs_status_idx ON agent_jobs(status)")
    db.execute("CREATE INDEX IF NOT EXISTS agent_jobs_run_idx ON agent_jobs(run_id)")
    # Migrate older deployments whose CHECK constraint predates 'cancelled'.
    try:
        db.execute("ALTER TABLE agent_jobs DROP CONSTRAINT IF EXISTS agent_jobs_status_check")
        db.execute(
            "ALTER TABLE agent_jobs ADD CONSTRAINT agent_jobs_status_check "
            "CHECK (status IN ('pending','running','done','error','cancelled'))"
        )
    except Exception:
        pass


def enqueue(run_id: int, question: str, tool: str, model: str, from_ui: bool) -> int:
    row = db.query(
        """
        INSERT INTO agent_jobs (run_id, question, tool, model, from_ui)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (run_id, question, tool, model, from_ui),
        one=True,
    )
    return int(row["id"])


def get(job_id: int) -> dict[str, Any] | None:
    return db.query("SELECT * FROM agent_jobs WHERE id = %s", (job_id,), one=True)


def claim_next() -> dict[str, Any] | None:
    """Atomically claim one pending job.

    FOR UPDATE SKIP LOCKED means two workers polling at the same instant can
    never grab the same row: the loser simply skips it and takes the next.
    That is the entire concurrency-control story, and it is why we do not need
    Redis here.
    """
    return db.query(
        """
        UPDATE agent_jobs SET status = 'running', started_at = now()
        WHERE id = (
            SELECT id FROM agent_jobs
            WHERE status = 'pending'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING *
        """,
        one=True,
    )


def complete(job_id: int, answer: str, citations: list | None) -> None:
    db.execute(
        """
        UPDATE agent_jobs
        SET status = 'done', answer = %s, citations = %s, finished_at = now()
        WHERE id = %s
        """,
        (answer, json.dumps(citations or []), job_id),
    )


def fail(job_id: int, error: str) -> None:
    db.execute(
        "UPDATE agent_jobs SET status = 'error', error = %s, finished_at = now() WHERE id = %s",
        (error, job_id),
    )


def cancel(job_id: int) -> bool:
    """Mark a pending or running job as cancelled. Returns True if it changed state."""
    row = db.query(
        """
        UPDATE agent_jobs
           SET status = 'cancelled', error = 'cancelled by user', finished_at = now()
         WHERE id = %s AND status IN ('pending', 'running')
        RETURNING id
        """,
        (job_id,),
        one=True,
    )
    return row is not None


def reap_stale() -> int:
    """Fail jobs whose worker died, so pollers get a terminal state."""
    conn = db._acquire()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_jobs
                SET status = 'error',
                    error = %s,
                    finished_at = now()
                WHERE status = 'running'
                  AND started_at < now() - (%s || ' seconds')::interval
                RETURNING id
                """,
                (
                    f"worker abandoned this job: no completion within "
                    f"{AGENT_JOB_TIMEOUT_S}s (restart or crash)",
                    AGENT_JOB_TIMEOUT_S,
                ),
            )
            rows = cur.fetchall() if cur.description else []
        conn.commit()
        return len(rows)
    finally:
        db.pool().putconn(conn)
        db._slots.release()


def queue_depth() -> dict[str, int]:
    """Pending/running counts -- used by /api/capacity and the 429 hint."""
    row = db.query(
        """
        SELECT
          COUNT(*) FILTER (WHERE status = 'pending') AS pending,
          COUNT(*) FILTER (WHERE status = 'running') AS running
        FROM agent_jobs
        """,
        one=True,
    )
    return {
        "pending": int(row["pending"]) if row else 0,
        "running": int(row["running"]) if row else 0,
    }