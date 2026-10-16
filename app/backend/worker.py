"""Agent worker: drains the agent_jobs queue.

Phase 2 runs this in-process as asyncio tasks; Phase 3 promotes it to a
dedicated compose service so the concurrency cap is global rather than
per-uvicorn-worker. The contract does not change between those two shapes --
which is the reason to put the queue in Postgres rather than in memory.

Concurrency model:
  * We run exactly AGENT_CONCURRENCY coroutines. Each claims one job at a time.
  * The AI CLI call itself is blocking (subprocess.run), so it is pushed to a
    worker thread via asyncio.to_thread. That thread is *dedicated to agent
    work* -- it is never a request thread, which is the whole point.
  * The number of live subprocesses is therefore bounded by construction
    (concurrency == semaphore width in ask.py), not by hope.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal

import db
import jobs
from ask import AGENT_CONCURRENCY, ask_report

# How often an idle worker checks for new work. Short enough to feel instant,
# long enough not to spin the database.
POLL_INTERVAL_S = float(os.environ.get("JOB_POLL_INTERVAL_S", "0.25"))
REAP_INTERVAL_S = float(os.environ.get("JOB_REAP_INTERVAL_S", "30"))


def _run_one(job: dict) -> None:
    """Execute a single claimed job. Runs in a worker thread."""
    job_id = job["id"]
    try:
        run = db.query("SELECT * FROM runs WHERE id = %s", (job["run_id"],), one=True)
        if not run:
            raise RuntimeError(f"run {job['run_id']} no longer exists")
        path = run.get("report_path")
        if not path or not os.path.isfile(path):
            raise RuntimeError("no report for this run")
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        history = db.list_conversations(job["run_id"])
        result = ask_report(text, job["question"], history, job["tool"], job["model"])
        jobs.complete(job_id, result["answer"], result["citations"])
        # Mirror the old inline behaviour: only questions raised from the UI
        # become visible conversation history.
        if job.get("from_ui"):
            db.add_conversation(
                job["run_id"],
                job["question"],
                result["answer"],
                result["model"],
                result["citations"],
            )
    except Exception as exc:  # noqa: BLE001 - the job must never die silently
        jobs.fail(job_id, f"{type(exc).__name__}: {exc}")


async def _worker_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            job = await asyncio.to_thread(jobs.claim_next)
        except Exception as exc:  # DB blip -- back off rather than spin
            print(f"[worker] claim failed: {exc}", flush=True)
            await asyncio.sleep(1.0)
            continue
        if job is None:
            await asyncio.sleep(POLL_INTERVAL_S)
            continue
        await asyncio.to_thread(_run_one, job)


async def _reaper_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.sleep(REAP_INTERVAL_S)
            reaped = await asyncio.to_thread(jobs.reap_stale)
            if reaped:
                print(f"[worker] reaped {reaped} abandoned job(s)", flush=True)
        except Exception as exc:
            print(f"[worker] reap failed: {exc}", flush=True)


async def run() -> None:
    """Start the worker set. Returns once tasks are scheduled."""
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover
            pass

    tasks = []
    for i in range(AGENT_CONCURRENCY):
        tasks.append(asyncio.create_task(_worker_loop(stop), name=f"agent-worker-{i}"))
    tasks.append(asyncio.create_task(_reaper_loop(stop), name="job-reaper"))
    print(f"[worker] {AGENT_CONCURRENCY} agent workers started", flush=True)

    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    # Standalone worker process (used by the Phase 3 compose service).
    jobs.ensure_agent_jobs_table()
    asyncio.run(run())