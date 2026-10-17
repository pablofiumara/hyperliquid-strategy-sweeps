"""Semantic retrieval over strategy reports: chunk -> embed -> cosine top-k.

Ask used to rank report chunks by keyword overlap alone, so a question phrased
in different words than the report ("stop loss" vs "protective exit") retrieved
poor context. Here every report is chunked once and each chunk is embedded with
the local Ollama model (nomic-embed-text by default), cached in Postgres by
(text sha1, model) so a text is embedded exactly once; a question then costs
one embed call plus a cosine scan over the run's handful of chunk vectors.

This is prompt-viewer's LangChain index without the dependency: report_chunks
is the document store, embedding_cache is the only place vectors live, and the
report files stay the source of truth -- both tables are derived data that can
be rebuilt at any time.

Best-effort by design: retrieve() returns None instead of raising when Ollama
is unreachable or the model is not pulled, and the caller falls back to the
keyword retriever, so /ask never breaks because the index is cold.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

import db

# Same host as the summary model: one local Ollama, no external API.
OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1"
)
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
# One batch embedding 32 x ~900 chars is a few seconds on CPU; 60s is headroom,
# not an expectation.
EMBED_TIMEOUT_S = float(os.environ.get("EMBED_TIMEOUT_S", "60"))

EMBED_URL = OLLAMA_BASE_URL.rstrip("/") + "/embeddings"

# nomic-embed-text is trained with these task prefixes; without them document
# and query vectors live in different spaces and scores are meaningless.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

# Chunk sizes match the keyword retriever in ask.py so semantic and fallback
# excerpts are comparable.
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# One HTTP round-trip per this many texts. A fresh sweep is hundreds of
# chunks; one request per chunk would add minutes of round-trip overhead.
EMBED_BATCH = 32


# ---------------------------------------------------------------------------
# Chunking: paragraph -> line -> sentence -> raw slice, then pack.
#
# Fixed-size slicing (the old keyword retriever) cuts mid-word; embeddings are
# robust to that but a chunk that starts halfway through a sentence carries
# less meaning. Keep each unit whole when it fits and pack units up to
# CHUNK_SIZE with CHUNK_OVERLAP carried between chunks.
# ---------------------------------------------------------------------------

def _units(text: str) -> list[str]:
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        pieces = para.split("\n") if len(para) > CHUNK_SIZE else [para]
        for line in pieces:
            line = line.strip()
            if not line:
                continue
            if len(line) <= CHUNK_SIZE:
                units.append(line)
                continue
            for sent in re.split(r"(?<=[.!?])\s+", line):
                if len(sent) <= CHUNK_SIZE:
                    units.append(sent)
                else:
                    step = CHUNK_SIZE - CHUNK_OVERLAP
                    units.extend(
                        sent[i : i + CHUNK_SIZE] for i in range(0, len(sent), step)
                    )
    return units


def chunk_text(text: str) -> list[str]:
    """Split a report into overlapping chunks that respect boundaries."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    cur = ""
    for unit in _units(text):
        if cur and len(cur) + len(unit) + 1 > CHUNK_SIZE:
            out.append(cur)
            tail = cur[-CHUNK_OVERLAP:]
            cur = (
                f"{tail}\n{unit}" if len(tail) + len(unit) + 1 <= CHUNK_SIZE else unit
            )
        else:
            cur = f"{cur}\n{unit}" if cur else unit
    if cur.strip():
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# Storage.
# ---------------------------------------------------------------------------

def ensure_tables() -> None:
    """Runtime migration: init.sql only runs on first database creation."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS report_chunks (
            id          SERIAL PRIMARY KEY,
            run_id      INT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            chunk_index INT NOT NULL,
            text        TEXT NOT NULL,
            UNIQUE (run_id, chunk_index)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS report_chunks_run_idx ON report_chunks(run_id)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS embedding_cache (
            text_hash  TEXT NOT NULL,
            model      TEXT NOT NULL,
            embedding  JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (text_hash, model)
        )
        """
    )


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def _stored_chunks(run_id: int) -> list[str]:
    rows = db.query(
        "SELECT text FROM report_chunks WHERE run_id = %s ORDER BY chunk_index",
        (run_id,),
    )
    return [r["text"] for r in rows]


def sync_chunks(run_id: int, chunks: list[str]) -> bool:
    """Store `chunks` as the index documents of one run; write only on change.

    A shrink is handled too: rows beyond the new chunk count are deleted, so a
    shortened report can never keep answering out of stale tail chunks.
    """
    if _stored_chunks(run_id) == chunks:
        return False
    for i, text in enumerate(chunks):
        db.execute(
            """
            INSERT INTO report_chunks (run_id, chunk_index, text)
            VALUES (%s, %s, %s)
            ON CONFLICT (run_id, chunk_index) DO UPDATE SET text = EXCLUDED.text
            """,
            (run_id, i, text),
        )
    db.execute(
        "DELETE FROM report_chunks WHERE run_id = %s AND chunk_index >= %s",
        (run_id, len(chunks)),
    )
    return True


# ---------------------------------------------------------------------------
# Embeddings.
# ---------------------------------------------------------------------------

def _cached_vectors(hashes: list[str]) -> dict[str, list[float]]:
    if not hashes:
        return {}
    rows = db.query(
        "SELECT text_hash, embedding FROM embedding_cache "
        "WHERE model = %s AND text_hash = ANY(%s)",
        (EMBED_MODEL, hashes),
    )
    out: dict[str, list[float]] = {}
    for r in rows:
        emb = r["embedding"]
        out[r["text_hash"]] = json.loads(emb) if isinstance(emb, str) else emb
    return out


def _embed_http(texts: list[str]) -> list[list[float]]:
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    req = urllib.request.Request(
        EMBED_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT_S) as resp:
        payload = json.load(resp)
    data = sorted(payload["data"], key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in data]


def embed_texts(texts: list[str], prefix: str) -> tuple[list[list[float]], int]:
    """Embed `texts` (in input order), caching documents by (sha1, model).

    An edited chunk re-embeds only its changed text, and switching EMBED_MODEL
    can never mix vector spaces. Returns the vectors and how many were newly
    computed.
    """
    hashes = [text_hash(t) for t in texts]
    cache = _cached_vectors(hashes)
    missing = [(h, t) for h, t in zip(hashes, texts) if h not in cache]
    for i in range(0, len(missing), EMBED_BATCH):
        batch = missing[i : i + EMBED_BATCH]
        fresh = _embed_http([f"{prefix}{t}" for _, t in batch])
        for (h, _), vec in zip(batch, fresh):
            cache[h] = vec
            db.execute(
                """
                INSERT INTO embedding_cache (text_hash, model, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (text_hash, model) DO UPDATE SET
                    embedding = EXCLUDED.embedding, updated_at = now()
                """,
                (h, EMBED_MODEL, json.dumps(vec)),
            )
    return [cache[h] for h in hashes], len(missing)


def embed_query(text: str) -> list[float]:
    """Embed a question; never cached (queries are cheap and must stay fresh)."""
    return _embed_http([f"{QUERY_PREFIX}{text}"])[0]


# ---------------------------------------------------------------------------
# Index / retrieve.
# ---------------------------------------------------------------------------

def index_report(run_id: int, text: str) -> dict[str, int]:
    """Make one report retrievable: chunk, sync, embed whatever is missing."""
    chunks = chunk_text(text)
    changed = sync_chunks(run_id, chunks)
    embedded = 0
    if chunks:
        _, embedded = embed_texts(chunks, DOC_PREFIX)
    return {"chunks": len(chunks), "changed": int(changed), "embedded": embedded}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(
    run_id: int, text: str, question: str, k: int = 6
) -> Optional[list[tuple[int, str]]]:
    """Top-k chunks of one report by cosine similarity, as (index, text).

    Returns None -- never raises -- when the index is unavailable (Ollama
    down, model missing, DB trouble), so the caller can fall back to keyword
    retrieval instead of failing the ask.
    """
    try:
        chunks = chunk_text(text)
        if not chunks:
            return []
        sync_chunks(run_id, chunks)
        vectors, _ = embed_texts(chunks, DOC_PREFIX)
        query_vec = embed_query(question)
    except Exception as exc:  # noqa: BLE001 - fallback is the whole point
        print(f"[index] semantic retrieval unavailable ({exc}); keyword fallback", flush=True)
        return None
    scored = sorted(
        ((_cosine(query_vec, v), i) for i, v in enumerate(vectors)),
        key=lambda sv: (-sv[0], sv[1]),
    )
    return [(i, chunks[i]) for _, i in scored[:k]]


# ---------------------------------------------------------------------------
# Warm pass: embed every stored report off the request path.
# ---------------------------------------------------------------------------

def warm() -> dict[str, int]:
    """Index every real report that lacks chunks or vectors.

    A fresh sweep is hundreds of embeddings (minutes of CPU Ollama work), so
    this runs in a daemon thread, not in a request. Safe to run twice: chunk
    sync writes nothing when unchanged and the sha1 cache skips every vector
    already computed.
    """
    rows = db.query(
        "SELECT id, report_path FROM runs "
        "WHERE has_real_report AND report_path IS NOT NULL"
    )
    reports = chunks = embedded = 0
    for row in rows:
        path = Path(row["report_path"])
        if not path.is_file():
            continue
        stats = index_report(row["id"], path.read_text(errors="replace"))
        if not stats["chunks"]:
            continue
        reports += 1
        chunks += stats["chunks"]
        embedded += stats["embedded"]
    return {"reports": reports, "chunks": chunks, "embedded": embedded}


def _available_models() -> Optional[list[str]]:
    """Model ids Ollama currently serves; None when it is unreachable."""
    url = OLLAMA_BASE_URL.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return [m.get("id", "") for m in json.load(resp).get("data", [])]
    except Exception:  # noqa: BLE001
        return None


def _model_pulled(models: list[str]) -> bool:
    want = EMBED_MODEL.split(":", 1)[0]
    return any(m.split(":", 1)[0] == want for m in models)


_warm_lock = threading.Lock()
_warm_running = False


def warm_async() -> bool:
    """Kick a background warm pass (single-flight). False if one is running."""
    global _warm_running
    with _warm_lock:
        if _warm_running:
            return False
        _warm_running = True

    def _run() -> None:
        global _warm_running
        try:
            models = _available_models()
            if models is None:
                print("[index] warm skipped: Ollama unreachable", flush=True)
            elif not _model_pulled(models):
                print(
                    f"[index] warm skipped: embed model '{EMBED_MODEL}' is not "
                    f"pulled (`ollama pull {EMBED_MODEL}`)",
                    flush=True,
                )
            else:
                t0 = time.monotonic()
                stats = warm()
                dt = time.monotonic() - t0
                print(f"[index] warm done in {dt:.1f}s: {stats}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a failed warm must never kill the app
            print(f"[index] warm failed: {exc}", flush=True)
        finally:
            with _warm_lock:
                _warm_running = False

    threading.Thread(target=_run, name="vector-index-warm", daemon=True).start()
    return True
