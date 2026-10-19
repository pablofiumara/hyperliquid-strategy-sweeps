"""Semantic retrieval over strategy reports, backed by LangChain.

Chunking uses LangChain's ``RecursiveCharacterTextSplitter``, embeddings come
from LangChain's ``OllamaEmbeddings`` (local Ollama, free), and ranking is
done by LangChain's ``InMemoryVectorStore``. Vectors are still cached in
Postgres by (text sha1, model) so a text is embedded exactly once.

Best-effort by design: retrieve() returns None instead of raising when Ollama
is unreachable or the model is not pulled, so the caller falls back to the
keyword retriever and /ask never breaks because the index is cold.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

import db

# Same host as the summary model: one local Ollama, no external API. The env
# value is OpenAI-compatible (/v1); LangChain's Ollama client wants the root.
OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1"
)
OLLAMA_ROOT = OLLAMA_BASE_URL.removesuffix("/v1").rstrip("/")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT_S = float(os.environ.get("EMBED_TIMEOUT_S", "60"))

# Chunk sizes match the keyword retriever in ask.py so semantic and fallback
# excerpts are comparable.
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# nomic-embed-text is trained with these task prefixes; without them document
# and query vectors live in different spaces and scores are meaningless.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_text(text: str) -> list[str]:
    """Split a report into overlapping chunks that respect boundaries."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return [c for c in _splitter.split_text(text) if c.strip()]


# ---------------------------------------------------------------------------
# Storage (unchanged schema).
# ---------------------------------------------------------------------------

def ensure_tables() -> None:
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
# Embeddings (LangChain + Postgres cache).
# ---------------------------------------------------------------------------

_raw_embedder: Optional[OllamaEmbeddings] = None


def _raw_embeddings() -> OllamaEmbeddings:
    global _raw_embedder
    if _raw_embedder is None:
        _raw_embedder = OllamaEmbeddings(
            model=EMBED_MODEL, base_url=OLLAMA_ROOT, validate_model_on_init=False
        )
    return _raw_embedder


class CachedEmbeddings(Embeddings):
    def __init__(self, embedder: Optional[Embeddings] = None) -> None:
        self.embedder = embedder if embedder is not None else _raw_embeddings()

    def cached(self, hashes: list[str]) -> dict[str, list[float]]:
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

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        hashes = [text_hash(t) for t in texts]
        cache = self.cached(hashes)
        missing = [(h, t) for h, t in zip(hashes, texts) if h not in cache]
        if missing:
            fresh = self.embedder.embed_documents(
                [f"{DOC_PREFIX}{t}" for _, t in missing]
            )
            for (h, _), vec in zip(missing, fresh):
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
        return [cache[h] for h in hashes]

    def embed_query(self, text: str) -> list[float]:
        return self.embedder.embed_query(f"{QUERY_PREFIX}{text}")


def embeddings() -> CachedEmbeddings:
    return CachedEmbeddings()


def embed_texts(texts: list[str], prefix: str) -> tuple[list[list[float]], int]:
    # `prefix` is retained for API compatibility; prefixes are applied inside
    # CachedEmbeddings based on document vs. query.
    hashes = [text_hash(t) for t in texts]
    cache = CachedEmbeddings().cached(hashes)
    missing = [(h, t) for h, t in zip(hashes, texts) if h not in cache]
    vectors = CachedEmbeddings().embed_documents(texts)
    return vectors, len(missing)


def embed_query(text: str) -> list[float]:
    return embeddings().embed_query(text)


# ---------------------------------------------------------------------------
# Index / retrieve.
# ---------------------------------------------------------------------------

def index_report(run_id: int, text: str) -> dict[str, int]:
    chunks = chunk_text(text)
    changed = sync_chunks(run_id, chunks)
    embedded = 0
    if chunks:
        _, embedded = embed_texts(chunks, DOC_PREFIX)
    return {"chunks": len(chunks), "changed": int(changed), "embedded": embedded}


def retrieve(
    run_id: int, text: str, question: str, k: int = 6
) -> Optional[list[tuple[int, str]]]:
    try:
        chunks = chunk_text(text)
        if not chunks:
            return []
        sync_chunks(run_id, chunks)
        docs = [Document(page_content=c, metadata={"index": i}) for i, c in enumerate(chunks)]
        store = InMemoryVectorStore.from_documents(docs, embeddings())
        hits = store.similarity_search(question, k=k)
    except Exception as exc:  # noqa: BLE001 - fallback is the whole point
        print(f"[index] semantic retrieval unavailable ({exc}); keyword fallback", flush=True)
        return None
    return [(d.metadata["index"], d.page_content) for d in hits]


# ---------------------------------------------------------------------------
# Warm pass.
# ---------------------------------------------------------------------------

def warm() -> dict[str, int]:
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
    url = OLLAMA_ROOT + "/v1/models"
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=5) as resp:
            import json as _json

            return [m.get("id", "") for m in _json.load(resp).get("data", [])]
    except Exception:  # noqa: BLE001
        return None


def _model_pulled(models: list[str]) -> bool:
    want = EMBED_MODEL.split(":", 1)[0]
    return any(m.split(":", 1)[0] == want for m in models)


_warm_lock = threading.Lock()
_warm_running = False


def warm_async() -> bool:
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
        except Exception as exc:  # noqa: BLE001
            print(f"[index] warm failed: {exc}", flush=True)
        finally:
            with _warm_lock:
                _warm_running = False

    threading.Thread(target=_run, name="vector-index-warm", daemon=True).start()
    return True
