import asyncio
import contextlib
import os
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import db
import jobs
import perf
import worker
from errors import ApiError
from importer import DATA_DIR, import_all
from cleanup import cleanup_all, cleanup_wallet
from ask import ask_report, agent_capacity, is_free_model, list_free_models


def _norm_summary(row):
    if not row:
        return None
    row = dict(row)
    if hasattr(row.get("generated_at"), "isoformat"):
        row["generated_at"] = row["generated_at"].isoformat()
    return row


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema migrations are NOT soft-fail. A partially applied migration used
    # to be swallowed by the same try/except as the optional filesystem import,
    # which left the app running with a missing trigger and silently wrong
    # scores. Fail fast and loudly instead.
    db.ensure_conversations_table()
    db.ensure_global_score()
    jobs.ensure_agent_jobs_table()
    # The filesystem import is genuinely optional: the UI should still boot if
    # the data directory is unavailable, so it degrades on its own.
    try:
        import_all()
    except Exception as e:
        print(f"startup import skipped: {e}")
    # Drain the agent job queue in-process ONLY when no dedicated worker
    # service is running. With the agent-worker service up, the backend must
    # stay a pure API tier: two sets of workers would double the number of
    # live agent subprocesses. Set RUN_WORKER_IN_API=1 to run them inline
    # (useful for a single-container dev run).
    run_inline = os.environ.get("RUN_WORKER_IN_API", "0") == "1"
    worker_task = None
    if run_inline:
        worker_task = asyncio.create_task(worker.run(), name="agent-workers")
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task


app = FastAPI(title="Hyperliquid Strategy Sweep", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
_perf_stats = perf.install(app)

# Origins the browser app can legitimately be served from. A question is only
# persisted into visible history if it arrives from one of these AND declares
# X-Client: ui -- see the /ask handler.
_ALLOWED_UI_ORIGINS = {
    f"http://localhost:{p}" for p in ("8080", "80")
} | {f"http://127.0.0.1:{p}" for p in ("8080", "80")}


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    """Turn any deliberate ApiError into its structured envelope.

    Registered globally so an ApiError raised deep inside db.py or ask.py
    arrives at the caller as an actionable 429/503 instead of being swallowed
    by FastAPI's default 500 handler.
    """
    return exc.to_response()


class Rating(BaseModel):
    value: int  # +1 interesting, -1 not, 0 = undo (delete rating)


class AskRequest(BaseModel):
    question: str
    tool: str | None = None
    model: str | None = None


@app.post("/api/import")
def do_import():
    return import_all()


@app.get("/api/models/free")
def free_models():
    return list_free_models()


@app.get("/api/capacity")
def capacity():
    """Agent slot usage + queue depth -- lets a client check before it fires,
    instead of discovering saturation via a 429."""
    cap = agent_capacity()
    depth = jobs.queue_depth()
    return {**cap, "queue_pending": depth["pending"], "queue_running": depth["running"]}


@app.get("/api/perf")
def perf_snapshot():
    """Rolling per-route latency, newest-worst-first.

    Percentiles come from the retained sample buffer; ``in_flight`` is the
    requests currently executing and is what shows the threadpool ceiling
    while the k6 load test is running.
    """
    routes = [{ "route": k, **v.snapshot()} for k, v in _perf_stats.items()]
    routes.sort(key=lambda r: r["p95_ms"], reverse=True)
    return {"routes": routes, "window_samples": perf._MAX_SAMPLES}


@app.post("/api/perf/reset")
def perf_reset():
    _perf_stats.clear()
    return {"ok": True}


@app.get("/api/perf/queries")
def perf_queries(limit: int = 15):
    """Slowest queries Postgres has actually executed (pg_stat_statements).

    Unlike the in-process request timer, this is measured by the database
    itself, so it catches query cost the app never sees (e.g. a full-table
    aggregate that happens to be fast only because the table is tiny today).
    """
    return db.query(
        """
        SELECT calls,
               round(total_exec_time::numeric, 1)              AS total_ms,
               round(mean_exec_time::numeric, 2)               AS mean_ms,
               round(max_exec_time::numeric, 1)                AS max_ms,
               rows,
               left(query, 160)                               AS query
        FROM pg_stat_statements
        -- pattern is parameterised on purpose: a literal percent sign
        -- anywhere in this SQL string (even in a comment) is parsed by
        -- psycopg2 as a format placeholder and raises IndexError.
        WHERE query NOT LIKE %s
        ORDER BY total_exec_time DESC
        LIMIT %s
        """,
        ("%" + "pg_stat_statements" + "%", limit),
    )


@app.get("/api/wallets")
def wallets():
    return db.query(
        """
        SELECT w.address, COUNT(r.id) AS runs,
               COUNT(*) FILTER (WHERE r.has_real_report) AS done
        FROM wallets w LEFT JOIN runs r ON r.wallet = w.address
        GROUP BY w.address ORDER BY w.address
        """
    )


@app.get("/api/wallets/{address}/runs")
def wallet_runs(address: str):
    """Runs for one wallet.

    global_score comes straight off the runs row (maintained by a trigger on
    ratings). It used to be a correlated subquery that re-aggregated every
    rating for the model on every row, which made this the hottest query in the
    app for no benefit -- see docs/BASELINE.md.
    """
    return db.query(
        """
        SELECT r.id, r.label, r.tool, r.model, r.variant, r.status,
               r.duration_s, r.bytes, r.context_size,
               COALESCE(rt.value, 0)  AS my_rating,
               r.global_score,
                r.has_real_report      AS has_report,
                CASE
                    WHEN r.has_real_report THEN 'DONE'
                    WHEN r.status = 'DONE' AND NOT r.has_real_report THEN 'FAILED'
                    ELSE r.status
                END                    AS display_status
        FROM runs r
        LEFT JOIN ratings rt ON rt.run_id = r.id
        WHERE r.wallet = %s
        ORDER BY r.global_score DESC, COALESCE(r.context_size, 0) DESC,
              (r.status = 'DONE') DESC, r.label
        """,
        (address,),
    )


def _enrich_run(run):
    """Attach the model's global score across all wallets to a run row.

    The score is now denormalised onto runs by a trigger on ratings, so this
    is a plain column read rather than a per-call aggregation.
    """
    run = dict(run)
    run["global_score"] = run.get("global_score") or 0
    # DONE requires a real strategy report; a DONE run without one is
    # surfaced as FAILED so the UI never shows DONE with "No report".
    status = run.get("status")
    has_report = bool(run.get("has_real_report"))
    if has_report:
        run["display_status"] = "DONE"
    elif status == "DONE":
        run["display_status"] = "FAILED"
    else:
        run["display_status"] = status
    return run


@app.get("/api/runs/{run_id}")
def run_detail(run_id: int):
    run = db.query("SELECT * FROM runs WHERE id = %s", (run_id,), one=True)
    if not run:
        raise HTTPException(404, "run not found")
    run["has_report"] = bool(run.get("has_real_report"))
    report = None
    if run["report_path"]:
        p = pathlib.Path(run["report_path"])
        if p.is_file():
            report = p.read_text(errors="replace")
    rating = db.query(
        "SELECT value FROM ratings WHERE run_id = %s", (run_id,), one=True
    )
    return {**_enrich_run(run), "report": report,
            "my_rating": rating["value"] if rating else 0}


@app.get("/api/wallets/{address}/runs/{label}")
def run_detail_by_label(address: str, label: str):
    """Fetch one run by (wallet, label) -- the URL is label-based now."""
    run = db.query(
        "SELECT * FROM runs WHERE wallet = %s AND label = %s",
        (address, label),
        one=True,
    )
    if not run:
        raise HTTPException(404, "run not found")
    run["has_report"] = bool(run.get("has_real_report"))
    report = None
    if run["report_path"]:
        p = pathlib.Path(run["report_path"])
        if p.is_file():
            report = p.read_text(errors="replace")
    rating = db.query(
        "SELECT value FROM ratings WHERE run_id = %s", (run["id"],), one=True
    )
    return {**_enrich_run(run), "report": report,
            "my_rating": rating["value"] if rating else 0}


@app.post("/api/runs/{run_id}/rating")
def rate(run_id: int, body: Rating):
    if body.value not in (-1, 0, 1):
        raise HTTPException(422, "value must be -1, 0, or 1")
    if not db.query("SELECT id FROM runs WHERE id = %s", (run_id,), one=True):
        raise HTTPException(404, "run not found")
    if body.value == 0:
        db.execute("DELETE FROM ratings WHERE run_id = %s", (run_id,))
    else:
        db.execute(
            """
            INSERT INTO ratings (run_id, value) VALUES (%s, %s)
            ON CONFLICT (run_id) DO UPDATE
                SET value = EXCLUDED.value, updated_at = now()
            """,
            (run_id, body.value),
        )
    # global_score is refreshed by the ratings trigger, so read it back rather
    # than re-aggregating here.
    model_row = db.query("SELECT model FROM runs WHERE id = %s", (run_id,), one=True)
    score = db.get_run_global_score(model_row["model"]) if model_row else 0
    return {"ok": True, "model_global_score": score}


@app.get("/api/duration-ranking")
def duration_ranking():
    return db.query(
        """
        SELECT r.tool,
               r.model,
               MIN(r.label)            AS label,
               COUNT(*)                AS runs,
               COUNT(DISTINCT r.wallet) AS wallets,
               COALESCE(SUM(r.duration_s), 0) AS total_s,
               COALESCE(AVG(r.duration_s), 0) AS avg_s
        FROM runs r
        WHERE r.duration_s IS NOT NULL AND r.duration_s > 0
          AND r.has_real_report = TRUE
        GROUP BY r.tool, r.model
        ORDER BY total_s ASC, r.model ASC
        """
    )


@app.get("/api/leaderboard")
def leaderboard():
    return db.query(
        """
        SELECT r.model,
               SUM(COALESCE(rt.value, 0))            AS score,
               COUNT(rt.value) FILTER (WHERE rt.value = 1)  AS positives,
               COUNT(rt.value) FILTER (WHERE rt.value = -1) AS negatives,
               COUNT(DISTINCT r.wallet)              AS wallets,
               COUNT(*)                              AS runs,
               MAX(r.context_size)                   AS context_size
        FROM runs r LEFT JOIN ratings rt ON rt.run_id = r.id
        WHERE r.model IS NOT NULL
        GROUP BY r.model
        ORDER BY score DESC, positives DESC,
                 COALESCE(MAX(r.context_size), 0) DESC, r.model
        """
    )


@app.get("/api/runs/{run_id}/conversations")
def conversations(run_id: int):
    if not db.query("SELECT id FROM runs WHERE id = %s", (run_id,), one=True):
        raise HTTPException(404, "run not found")
    rows = db.list_conversations(run_id)
    out = []
    for r in rows:
        r = dict(r)
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
        out.append(r)
    return out


@app.post("/api/runs/{run_id}/ask", status_code=202)
def ask_run(run_id: int, body: AskRequest, request: Request):
    """Queue a follow-up question for an AI agent.

    Returns 202 immediately. The agent can take up to 300s, so the request
    deliberately does NOT wait for it -- holding a server thread for that long
    was what starved every other endpoint (docs/BASELINE.md). Subscribe to
    /api/jobs/{id}/stream for the answer, or poll /api/jobs/{id}.

    Validation still happens synchronously, so a caller still learns
    immediately -- with a structured error -- whether the run exists, whether
    it has a report, and whether the chosen model is really free.
    """
    run = db.query("SELECT * FROM runs WHERE id = %s", (run_id,), one=True)
    if not run:
        raise HTTPException(404, "run not found")
    path = run.get("report_path")
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "no report for this run")
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(422, "question is empty")
    free = list_free_models()
    tool = body.tool
    model = body.model
    if (tool or model) and not is_free_model(tool, model):
        raise HTTPException(422, "selected model is not a free $0 model")
    if not tool or not model:
        if not free:
            raise HTTPException(503, "no free models available")
        tool = free[0]["tool"]
        model = free[0]["model"]
    # Only questions raised by the app's own UI are persisted as visible
    # conversation history. The X-Client header is caller-controlled, so a
    # script that sets it (a test, a curl, another tool) must not be able to
    # inject itself into the user's history -- we additionally require the
    # request to come from our own origin. Everything else is treated as a
    # non-UI caller and stored only as a job.
    claimed_ui = request.headers.get("x-client") == "ui"
    same_origin = (request.headers.get("origin") or "") in _ALLOWED_UI_ORIGINS
    from_ui = claimed_ui and same_origin

    # Backpressure: refuse new work once the backlog is deep enough that the
    # answer would arrive long after the caller stopped caring. Better a
    # clear 429 with a position than an answer in three hours.
    depth = jobs.queue_depth()
    if depth["pending"] >= jobs.MAX_QUEUE_DEPTH:
        raise ApiError(
            429,
            "agent_queue_full",
            "The agent queue is full. Too many questions are already waiting.",
            what=(
                f"{depth['pending']} job(s) pending, limit is "
                f"{jobs.MAX_QUEUE_DEPTH}. {depth['running']} agent(s) running."
            ),
            fix=(
                "Wait until the backlog drains and retry. Nothing was queued "
                "by this request and no state changed."
            ),
            next_actions=[
                "Retry after a delay.",
                "GET /api/capacity to watch queue_pending fall before retrying.",
                "Ask fewer follow-ups concurrently.",
            ],
            headers={"Retry-After": "15"},
            extra={
                "pending": depth["pending"],
                "running": depth["running"],
                "limit": jobs.MAX_QUEUE_DEPTH,
            },
        )

    job_id = jobs.enqueue(run_id, question, tool, model, from_ui)
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "pending",
            "poll_url": f"/api/jobs/{job_id}",
            "stream_url": f"/api/jobs/{job_id}/stream",
        },
    )


def _job_view(job: dict) -> dict:
    out = {
        "job_id": job["id"],
        "status": job["status"],
        "tool": job["tool"],
        "model": job["model"],
        "created_at": job["created_at"].isoformat() if job.get("created_at") else None,
    }
    if job["status"] == "done":
        out["answer"] = job["answer"]
        out["citations"] = job.get("citations") or []
    if job["status"] == "error":
        out["error"] = job.get("error") or "agent failed"
    return out


@app.get("/api/jobs/{job_id}")
def job_status(job_id: int):
    job = jobs.get(job_id)
    if not job:
        raise ApiError(
            404,
            "job_not_found",
            f"No agent job with id {job_id}.",
            fix="Use the job_id returned when you POSTed to /api/runs/{id}/ask.",
            next_actions=["POST /api/runs/{run_id}/ask to create a new job."],
        )
    return _job_view(job)


@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: int, request: Request):
    """Server-Sent Events: pending -> running -> done|error.

    One event per state change, then the stream closes. A client that only
    wants the answer can ignore the intermediate events and read the terminal
    one.
    """
    job = jobs.get(job_id)
    if not job:
        raise ApiError(
            404,
            "job_not_found",
            f"No agent job with id {job_id}.",
            fix="Use the job_id returned when you POSTed to /api/runs/{id}/ask.",
            next_actions=["POST /api/runs/{run_id}/ask to create a new job."],
        )

    async def events():
        import json as _json

        seen = None
        while True:
            if await request.is_disconnected():
                return
            current = jobs.get(job_id)
            if current is None:
                return
            status = current["status"]
            if status != seen:
                seen = status
                yield f"event: {status}\ndata: {_json.dumps(_job_view(current))}\n\n"
            if status in ("done", "error"):
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",  # stop nginx from buffering the stream
        },
    )


@app.get("/api/wallets/{address}/summary")
def wallet_summary(address: str):
    return _norm_summary(db.get_summary(address))


@app.post("/api/wallets/{address}/summary")
def generate_wallet_summary(address: str):
    from summary import generate_summary

    wdir = DATA_DIR / address
    if not wdir.is_dir():
        raise HTTPException(404, "wallet not found")
    data = generate_summary(wdir)
    if data.get("error"):
        raise HTTPException(502, f"Ollama failed: {data['error']}")
    db.save_summary(data)
    # The model's answer is now captured in strategy_report.md; purge the
    # disposable scratch (raw API dumps, scripts, duplicate reports) so the
    # workspace stays small and one-fact-one-file holds.
    cleanup_wallet(address)
    return _norm_summary(db.get_summary(address))


@app.post("/api/wallets/{address}/cleanup")
def wallet_cleanup(address: str):
    return cleanup_wallet(address)


@app.post("/api/cleanup")
def global_cleanup():
    return cleanup_all()
