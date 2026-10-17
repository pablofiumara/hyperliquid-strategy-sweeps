import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import vector_index
from errors import capacity_exhausted

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

ROUTER_RE = True

# ---------------------------------------------------------------------------
# Agent concurrency cap.
#
# Every agent call runs a Node CLI subprocess that can live for 300s. Without a
# cap, N concurrent asks spawn N of those processes and the box thrashes. The
# cap makes overload explicit: a caller waits briefly for a slot, then gets a
# structured 429 telling it exactly when to come back.
#
# This is a threading (not asyncio) semaphore because ask_report/_run_cli are
# synchronous and run inside Starlette's threadpool.
# ---------------------------------------------------------------------------
AGENT_CONCURRENCY = int(os.environ.get("AGENT_CONCURRENCY", "6"))
AGENT_SLOT_WAIT_SECONDS = float(os.environ.get("AGENT_SLOT_WAIT_SECONDS", "5"))
AGENT_RETRY_AFTER_SECONDS = int(os.environ.get("AGENT_RETRY_AFTER_SECONDS", "10"))

_agent_slots = threading.BoundedSemaphore(AGENT_CONCURRENCY)
_agent_lock = threading.Lock()
_agent_in_use = 0


def agent_capacity() -> dict[str, int]:
    with _agent_lock:
        return {
            "capacity": AGENT_CONCURRENCY,
            "in_use": _agent_in_use,
            "free": max(0, AGENT_CONCURRENCY - _agent_in_use),
        }


class _AgentSlot:
    """Context manager that holds one of the agent slots or raises a 429."""

    def __enter__(self):
        waited = time.monotonic()
        if not _agent_slots.acquire(timeout=AGENT_SLOT_WAIT_SECONDS):
            waited_s = time.monotonic() - waited
            cap = agent_capacity()
            raise capacity_exhausted(
                capacity=cap["capacity"],
                in_use=cap["in_use"],
                waited_s=waited_s,
                retry_after_s=AGENT_RETRY_AFTER_SECONDS,
            )
        self.waited_s = time.monotonic() - waited
        global _agent_in_use
        with _agent_lock:
            _agent_in_use += 1
        return self

    def __exit__(self, *exc):
        global _agent_in_use
        with _agent_lock:
            _agent_in_use -= 1
        _agent_slots.release()
        return False

# ---------------------------------------------------------------------------
# Free-model list cache (TTL + single-flight).
#
# The free list is expensive to build: when the cached free_{tool}.txt files
# are missing or empty, _generate_free_list shells out to each CLI (up to 180s
# per tool). list_free_models() used to run that on EVERY request, twice per
# /ask (main.py calls it directly, and is_free_model calls it again). A small
# TTL cache plus a lock collapses concurrent callers onto one fetch and keeps
# the hot path in microseconds. 300s is short enough that a model becoming
# paid (or newly free) is picked up quickly.
# ---------------------------------------------------------------------------
_FREE_TTL_SECONDS = 300.0
_free_cache: list[dict[str, Any]] | None = None
_free_cache_at: float = 0.0
_free_lock = threading.Lock()


def _cli_env() -> dict:
    env = os.environ.copy()
    extra = "/root/.npm-global/bin:/root/.kilo/bin:/root/.opencode/bin:/usr/local/bin"
    env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


def _ask_jobs_dir() -> str:
    return os.environ.get("ASK_JOBS_DIR", "/pv_ask_jobs")


def _read_free_file(tool: str) -> list[str]:
    path = os.path.join(_ask_jobs_dir(), f"free_{tool}.txt")
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(s)
    return out


def _is_router(model: str) -> bool:
    m = model.lower()
    return ("router" in m) or m.endswith("-auto") or "/auto" in m


def _generate_free_list(tool: str) -> list[str]:
    # Fall back to live CLI metadata when prompt-viewer's cached list is absent.
    if tool == "cline":
        return _read_free_file("cline")
    try:
        proc = subprocess.run(
            [tool, "models", "--verbose"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=180,
            env=_cli_env(),
        )
        p = subprocess.run(
            ["python3", "/srv/parse_free.py", tool],
            input=proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=60,
            env=_cli_env(),
        )
        return [x.strip() for x in p.stdout.splitlines() if x.strip()]
    except Exception:
        return []


def _build_free_models() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set()
    for tool in ("cline", "kilo", "opencode"):
        ids = _read_free_file(tool)
        if not ids:
            ids = _generate_free_list(tool)
        for model in ids:
            if _is_router(model):
                continue
            name = f"{tool}/{model}"
            if name in seen:
                continue
            seen.add(name)
            items.append(
                {
                    "tool": tool,
                    "model": model,
                    "name": name,
                    "free": True,
                    "price": "$0",
                }
            )
    return items


def list_free_models() -> list[dict[str, Any]]:
    """Free $0 models exposed by kilo/opencode/cline, TTL-cached.

    Returns a shallow copy so callers cannot mutate the cached list. On a
    transient build failure we deliberately do NOT cache the empty result --
    we serve the stale list (if any) so one bad probe cannot disable /ask for
    the whole TTL window.
    """
    global _free_cache, _free_cache_at
    now = time.monotonic()
    if _free_cache is not None and (now - _free_cache_at) < _FREE_TTL_SECONDS:
        return list(_free_cache)
    # Single-flight: only the first thread builds; the rest wait here and then
    # hit the fresh cache.
    with _free_lock:
        now = time.monotonic()
        if _free_cache is not None and (now - _free_cache_at) < _FREE_TTL_SECONDS:
            return list(_free_cache)
        items = _build_free_models()
        if items:
            _free_cache = items
            _free_cache_at = time.monotonic()
            return list(items)
        # Build failed (e.g. CLIs not reachable). Serve stale if we have it.
        if _free_cache is not None:
            return list(_free_cache)
        return []


def is_free_model(tool: str | None, model: str | None) -> bool:
    if not tool or not model:
        return False
    if _is_router(model):
        return False
    return any(
        m["tool"] == tool and m["model"] == model for m in list_free_models()
    )


def _chunks(text: str) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        out.append(text[i : i + CHUNK_SIZE])
        if i + CHUNK_SIZE >= n:
            break
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in out if c.strip()]


def _retrieve(text: str, question: str, k: int = 6) -> list[tuple[int, str]]:
    qs = set(re.findall(r"\w{3,}", question.lower()))
    scored = []
    for idx, c in enumerate(_chunks(text)):
        cl = c.lower()
        score = 0
        for t in qs:
            score += cl.count(t)
        if question.strip().lower() in cl:
            score += 5
        scored.append((score, idx, c))
    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = scored[:k]
    if not chosen or all(s == 0 for s, _, _ in chosen):
        chosen = [(0, idx, c) for idx, c in enumerate(_chunks(text)[:k])]
    return [(idx, c) for _, idx, c in chosen]


def _run_cli(tool: str, model: str, prompt: str, timeout: int = 300) -> str:
    work = tempfile.mkdtemp(prefix=f"ask-{tool}-", dir="/tmp")
    try:
        if tool == "cline":
            cmd = [
                "cline",
                "-P",
                "cline",
                "-m",
                model,
                "--auto-approve",
                "true",
                "-y",
                "-c",
                work,
                "--json",
                prompt,
            ]
        elif tool == "kilo":
            cmd = ["kilo", "run", "-m", model, "--auto", "--dir", work, prompt]
        else:
            cmd = ["opencode", "run", "-m", model, "--auto", "--dir", work, prompt]
        # Hold a slot only around the actual subprocess execution -- that is
        # the expensive, resource-hungry part. Prompt assembly happens outside.
        with _AgentSlot():
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                env=_cli_env(),
            )
        out = proc.stdout or ""
        if tool == "cline":
            tpath = os.path.join(work, "transcript.jsonl")
            with open(tpath, "w", encoding="utf-8") as f:
                f.write(out)
            try:
                ex = subprocess.run(
                    ["python3", "/srv/extract_submit.py", tpath],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=60,
                    env=_cli_env(),
                )
                if (ex.stdout or "").strip():
                    return ex.stdout.strip()
            except Exception:
                pass
        return out.strip()
    finally:
        import shutil

        shutil.rmtree(work, ignore_errors=True)


def ask_report(
    report: str,
    question: str,
    history: list[dict],
    tool: str,
    model: str,
    run_id: int | None = None,
) -> dict[str, Any]:
    # Semantic retrieval when the index is available; the keyword retriever is
    # the always-available fallback (retrieve returns None on any index
    # failure, e.g. Ollama unreachable).
    retrieved = None
    if run_id is not None:
        retrieved = vector_index.retrieve(run_id, report, question)
    if retrieved is None:
        retrieved = _retrieve(report, question)
    excerpts = "\n\n".join(
        f"--- Excerpt {i} ---\n{c}" for i, (_, c) in enumerate(retrieved, 1)
    )
    hist = ""
    if history:
        hist = "\n".join(f"Q: {h['question']}\nA: {h['answer']}" for h in history)
        hist = f"Conversation so far:\n{hist}\n\n"
    prompt = (
        "You are answering a follow-up question about one stored trading-strategy report.\n"
        "Use only the report excerpts and conversation history below. If the answer "
        "is not in the excerpts, say so clearly. Answer in stdout only; do not create files.\n\n"
        f"{hist}Relevant report excerpts:\n{excerpts}\n\nQuestion: {question}"
    )
    answer = _run_cli(tool, model, prompt)
    # strip ANSI escapes
    answer = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", answer).strip()
    if not answer:
        raise RuntimeError("agent produced no answer")
    return {"answer": answer, "citations": [i for i, _ in retrieved], "tool": tool, "model": model}
