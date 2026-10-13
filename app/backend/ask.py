import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from typing import Any

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

ROUTER_RE = True


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


def list_free_models() -> list[dict[str, Any]]:
    """Free $0 models exposed by kilo/opencode/cline."""
    free_dir = _ask_jobs_dir()
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
    report: str, question: str, history: list[dict], tool: str, model: str
) -> dict[str, Any]:
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
