import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from importer import DATA_DIR, import_all


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
        import_all()
    except Exception as e:  # db not ready yet -> frontend still boots
        print(f"startup import skipped: {e}")
    yield


app = FastAPI(title="Hyperliquid Strategy Sweep", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class Rating(BaseModel):
    value: int  # +1 interesting, -1 not


@app.post("/api/import")
def do_import():
    return import_all()


@app.get("/api/wallets")
def wallets():
    return db.query(
        """
        SELECT w.address, COUNT(r.id) AS runs,
               COUNT(*) FILTER (WHERE r.status='DONE') AS done
        FROM wallets w LEFT JOIN runs r ON r.wallet = w.address
        GROUP BY w.address ORDER BY w.address
        """
    )


@app.get("/api/wallets/{address}/runs")
def wallet_runs(address: str):
    return db.query(
        """
        SELECT r.id, r.label, r.tool, r.model, r.variant, r.status,
               r.duration_s, r.bytes,
               COALESCE(rt.value, 0)  AS my_rating,
               COALESCE(g.total, 0)   AS global_score,
               (report_path IS NOT NULL AND r.status = 'DONE') AS has_report
        FROM runs r
        LEFT JOIN ratings rt ON rt.run_id = r.id
        LEFT JOIN (
            SELECT r2.model, SUM(COALESCE(rt2.value, 0)) AS total
            FROM runs r2 LEFT JOIN ratings rt2 ON rt2.run_id = r2.id
            WHERE r2.model IS NOT NULL GROUP BY r2.model
        ) g ON g.model = r.model
        WHERE r.wallet = %s
        ORDER BY global_score DESC, (r.status = 'DONE') DESC, r.label
        """,
        (address,),
    )


@app.get("/api/runs/{run_id}")
def run_detail(run_id: int):
    run = db.query("SELECT * FROM runs WHERE id = %s", (run_id,), one=True)
    if not run:
        raise HTTPException(404, "run not found")
    report = None
    if run["report_path"]:
        p = pathlib.Path(run["report_path"])
        if p.is_file():
            report = p.read_text(errors="replace")
    rating = db.query(
        "SELECT value FROM ratings WHERE run_id = %s", (run_id,), one=True
    )
    return {**run, "report": report, "my_rating": rating["value"] if rating else 0}


@app.post("/api/runs/{run_id}/rating")
def rate(run_id: int, body: Rating):
    if body.value not in (-1, 1):
        raise HTTPException(422, "value must be -1 or 1")
    if not db.query("SELECT id FROM runs WHERE id = %s", (run_id,), one=True):
        raise HTTPException(404, "run not found")
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


@app.get("/api/leaderboard")
def leaderboard():
    return db.query(
        """
        SELECT r.model,
               SUM(COALESCE(rt.value, 0))            AS score,
               COUNT(rt.value) FILTER (WHERE rt.value = 1)  AS positives,
               COUNT(rt.value) FILTER (WHERE rt.value = -1) AS negatives,
               COUNT(DISTINCT r.wallet)              AS wallets,
               COUNT(*)                              AS runs
        FROM runs r LEFT JOIN ratings rt ON rt.run_id = r.id
        WHERE r.model IS NOT NULL
        GROUP BY r.model
        ORDER BY score DESC, positives DESC, r.model
        """
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
    return _norm_summary(db.get_summary(address))
