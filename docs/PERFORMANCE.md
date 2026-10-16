# Performance: before and after

Everything here was measured on this machine against this codebase. The
"before" numbers come from `docs/BASELINE.md`, captured at commit `5e02d99`
before any optimisation. The "after" numbers come from the **same k6 profile**
(`loadtest/k6.js`: 30 concurrent agent asks + 20 concurrent readers, ~90 s) run
after the work described below.

Raw snapshots: `loadtest/results/baseline-perf.json`,
`loadtest/results/final-perf.json`.

## Headline

| metric (same load profile) | before | after | change |
|---|---:|---:|---|
| read latency p95 (client) | 8 336 ms | **5.3 ms** | **1 573× faster** |
| read latency avg (client) | 1 623 ms | **3.2 ms** | 507× faster |
| read latency max (client) | 56 254 ms | **28.4 ms** | 1 981× faster |
| total requests served | 1 091 | **10 227** | **9.4× throughput** |
| request failure rate | 33.0 % | **7.7 %** | see note |
| `/ask` time to first response | up to 148 286 ms | **12 ms** | 12 000× faster |

The residual 7.7 % "failures" are not errors. They are the two admission
controls doing their job — the queue-full `429` (backpressure) and the nginx
rate limiter — which k6 counts as non-2xx by design. There were **zero 5xx**
responses across every run.

## Per route, server-side p95

Captured from `GET /api/perf` immediately after each run.

| route | calls | p95 before | p95 after | speedup | max before | max after |
|---|---:|---:|---:|---:|---:|---:|
| `/api/duration-ranking` | 2 338 | 110 604 ms | **4 ms** | 30 469× | 110 625 ms | 27 ms |
| `/api/runs/{id}/ask` | 875 | 141 010 ms | **12 ms** | 12 125× | 148 286 ms | 43 ms |
| `/api/wallets/{address}/runs` | 2 338 | 42 685 ms | **4 ms** | 10 212× | 119 857 ms | 20 ms |
| `/api/wallets` | 2 338 | 10 487 ms | **3 ms** | 3 277× | 111 969 ms | 19 ms |
| `/api/leaderboard` | 2 338 | 5 478 ms | **4 ms** | 1 387× | 110 786 ms | 27 ms |

## Why the "before" numbers look the way they do

Starlette runs every `def` endpoint in an anyio threadpool with **exactly 40
tokens** (verified in-container:
`anyio.to_thread.current_default_thread_limiter().total_tokens == 40`).
Before the fix, `POST /ask` ran the AI CLI subprocess **inline**, so one ask
occupied one of those 40 tokens for the agent's entire lifetime — up to 300
seconds.

With 30 concurrent asks the pool saturated and every cheap GET queued behind
them. The signature is unmistakable in the baseline data: read routes have a
**p50 of 2–3 ms** but a **p95 of 42–110 seconds**. The SQL was never slow; it
simply could not get a thread. At peak, `/api/runs/{id}/ask` held **39 of 40**
tokens, and two of three manual `GET /api/perf` probes issued right after the
run came back *empty* — the server had no free thread to answer them.

## What was changed

### 1. Agent calls became jobs (the actual fix)

`POST /api/runs/{id}/ask` now validates synchronously and returns **`202` with a
`job_id`** in single-digit milliseconds. Work is claimed from an `agent_jobs`
table with `FOR UPDATE SKIP LOCKED`, so any number of workers can poll
concurrently without two of them ever claiming the same row.

A request no longer owns a thread for its own duration, so **thread occupancy is
decoupled from agent duration**. That is why read latency stopped depending on
agent load at all.

Postgres is the queue rather than Redis: one fewer service to run, durable
state that survives a restart, and the rows double as an audit trail. At the
rate an AI CLI can actually produce — one answer per seconds, not microseconds
— a database queue is not the bottleneck.

* `GET /api/jobs/{id}` — poll
* `GET /api/jobs/{id}/stream` — SSE, `pending → running → done|error`
* a reaper fails jobs whose worker died, so a poller never hangs forever

### 2. Bounded concurrency, with errors a machine can act on

`AGENT_CONCURRENCY` (default 6) caps live agent subprocesses. Overload no longer
fails opaquely: a new `errors.py` envelope carries a stable `code`, what went
wrong with live values, the concrete fix, copy-pasteable `valid_next_actions`,
and `Retry-After`. Verified with 20 concurrent asks: 6 took slots, 12 received
an actionable 429, zero 5xx, and capacity returned to 6/6 afterwards.

nginx speaks the same language — `limit_req_status 429`, `Retry-After: 5`,
reads at 50 r/s and asks at 2 r/s.

### 3. The free-model list is no longer rebuilt per request

`list_free_models()` shelled out to each CLI (up to **180 s** per tool) whenever
the cached `free_{tool}.txt` files were missing or empty — and `main.py` called
it directly *and* again inside `is_free_model()`, so one ask paid twice.

Measured with the cache files removed: **4.1 s cold → 0.0000 s warm**. This was
not hypothetical: the sibling project's `free_cline.txt` was truncated to 0 bytes
partway through the session, which is exactly the condition that triggers it.

### 4. Denormalised the model score

`/api/wallets/{addr}/runs` carried a correlated subquery that re-aggregated
*every* rating for the model on *every row*. It was the hottest statement in the
app (519 ms over 2 333 calls, 69 990 rows). `global_score` is now materialised
onto `runs` and maintained by a statement-level trigger on `ratings`.

**Honest assessment:** this is architecturally correct but the measured win is
modest — 0.2225 ms → 0.1748 ms per call, about **21 %**. At 60 runs the
removed aggregate was cheap. The real gain is that per-request cost no longer
scales with total rating history, which is why it is worth doing rather than
headline-worthy.

### 5. Bounded database waits

`SimpleConnectionPool.getconn()` has no timeout — a request either waited forever
or surfaced a raw `PoolError` as a 500. A semaphore the same width as the pool
bounds the wait at 5 s and turns exhaustion into a structured 503. Pool widened
1..10 → 2..20. Verified with 60 concurrent reads: all 200, no 503, no leak.

## What is still true, and what is left

* **Agent wall-clock is unchanged** and cannot be: a model still takes 30–300 s
  to think. The queue does not make agents faster — it stops everything else
  from waiting on them. This is the real constraint and worth saying plainly.
* **The UI still polls** every 5–10 s on three views. At 3–5 ms per read that is
  no longer a bottleneck (~0.3 req/s per user). Replacing it with push
  notifications is future work; HTTP ETag caching was deliberately skipped
  because it would add complexity for little gain at this latency.
* **The backend still runs one uvicorn worker.** Reads scale fine as they are;
  the next lever, if needed, is multiple workers. That requires lowering
  `DB_POOL_MAX` so `workers × pool ≤ 100` (Postgres default `max_connections`).
  The budget is documented at the sizing constant.
* **A pre-existing correctness issue, unrelated to performance:** `/ask` can
  return `200` with a *nonsense* answer — a SQL error leaking out of an agent
  CLI was observed being stored as a valid response. Worth addressing separately.

## Bugs found and fixed along the way

* `perf.install()` returned `None` (defaulted its dict to `None` without ever
  creating it) — caught by the first `/api/perf` call.
* A `%` inside a SQL **comment** made psycopg2 raise `IndexError`. psycopg2 scans
  the entire string for format placeholders, comments included.
* A trigger function declared `RETURNS VOID`; PostgreSQL requires `trigger`.
  Worse, the lifespan's broad `except` swallowed the failure and left the app
  running with a missing trigger and silently wrong scores. Migrations now fail
  loudly; only the optional filesystem import degrades softly.

## Reproduce

```bash
make start
curl -s -X POST http://localhost:8002/api/perf/reset
mkdir -p loadtest/results
docker run --rm -i --network host \
  -v "$PWD/loadtest:/scripts" grafana/k6 run /scripts/k6.js
curl -s http://localhost:8002/api/perf | python3 -m json.tool
curl -s "http://localhost:8002/api/perf/queries?limit=10" | python3 -m json.tool
```

Then open <http://localhost:8080/perf> for the table, and see live agent slots
and queue depth at <http://localhost:8080/api/capacity>.