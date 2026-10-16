import os
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
import perf
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
    try:
        db.ensure_conversations_table()
        import_all()
    except Exception as e:  # db not ready yet -> frontend still boots
        print(f"startup import skipped: {e}")
    yield


app = FastAPI(title="Hyperliquid Strategy Sweep", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
_perf_stats = perf.install(app)


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
    """Agent slot usage -- lets a client check before it fires, not after a 429."""
    return agent_capacity()


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
    return db.query(
        """
        SELECT r.id, r.label, r.tool, r.model, r.variant, r.status,
               r.duration_s, r.bytes, r.context_size,
               COALESCE(rt.value, 0)  AS my_rating,
               COALESCE(g.total, 0)   AS global_score,
                r.has_real_report      AS has_report,
                CASE
                    WHEN r.has_real_report THEN 'DONE'
                    WHEN r.status = 'DONE' AND NOT r.has_real_report THEN 'FAILED'
                    ELSE r.status
                END                    AS display_status
        FROM runs r
        LEFT JOIN ratings rt ON rt.run_id = r.id
        LEFT JOIN (
            SELECT r2.model, SUM(COALESCE(rt2.value, 0)) AS total
            FROM runs r2 LEFT JOIN ratings rt2 ON rt2.run_id = r2.id
            WHERE r2.model IS NOT NULL GROUP BY r2.model
        ) g ON g.model = r.model
        WHERE r.wallet = %s
        ORDER BY global_score DESC, COALESCE(r.context_size, 0) DESC,
              (r.status = 'DONE') DESC, r.label
        """,
        (address,),
    )


def _enrich_run(run):
    """Attach the model's global score across all wallets to a run row."""
    score = db.query(
        """
        SELECT COALESCE(SUM(COALESCE(rt.value, 0)), 0) AS total
        FROM runs r LEFT JOIN ratings rt ON rt.run_id = r.id
        WHERE r.model = %s
        """,
        (run["model"],),
        one=True,
    )
    run = dict(run)
    run["global_score"] = score["total"] if score else 0
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
    score = db.query(
        """
        SELECT COALESCE(SUM(COALESCE(rt.value, 0)), 0) AS total
        FROM runs r LEFT JOIN ratings rt ON rt.run_id = r.id
        WHERE r.model = (SELECT model FROM runs WHERE id = %s)
        """,
        (run_id,),
        one=True,
    )
    return {"ok": True, "model_global_score": score["total"]}


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


@app.post("/api/runs/{run_id}/ask")
def ask_run(run_id: int, body: AskRequest, request: Request):
    run = db.query("SELECT * FROM runs WHERE id = %s", (run_id,), one=True)
    if not run:
        raise HTTPException(404, "run not found")
    path = run.get("report_path")
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "no report for this run")
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(422, "question is empty")
    text = open(path, encoding="utf-8", errors="replace").read()
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
    history = db.list_conversations(run_id)
    try:
        result = ask_report(text, question, history, tool, model)
    except ApiError as exc:
        # Structured 429/503 telling an autonomous caller what to do next.
        return exc.to_response()
    except Exception as exc:
        raise HTTPException(502, f"ask failed: {exc}")
    # Only asks from the app UI are stored; scripts/tests may call the
    # endpoint but must never leave visible conversations behind.
    if request.headers.get("x-client") == "ui":
        db.add_conversation(run_id, question, result["answer"], result["model"], result["citations"])
    return {
        "answer": result["answer"],
        "model": result["model"],
        "citations": result["citations"],
    }


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
