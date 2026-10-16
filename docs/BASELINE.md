# Phase 0 — Baseline measurement

Recorded before any optimisation, on the code as it stood at commit
`5e02d99`. Every number here is real output from the stack, not an estimate.

## Environment

| | |
|---|---|
| Host | 20 vCPU, 64 GB RAM, Linux |
| Stack | `docker compose` — Postgres 16, FastAPI backend (single uvicorn worker), nginx frontend |
| Backend host port | `8002` (compose maps `8002:8000`) |
| k6 | `grafana/k6` Docker image, no host install |
| DB state | 2 wallets, 60 runs (from `POST /api/import`) |

## The workload

`loadtest/k6.js` runs two scenarios against the backend directly:

* **askers** — 30 concurrent VUs hitting `POST /api/runs/1/ask`. Each ask spawns
  an AI CLI subprocess (`cline`/`kilo`/`opencode`) that can run for **300
  seconds**. The client abandons each request after 3s so VUs recycle; what
  matters is how much server capacity each ask consumes, not how long the agent
  thinks.
* **readers** — 20 concurrent VUs doing the four cheap GETs the UI polls
  (`/api/wallets`, `/api/wallets/{addr}/runs`, `/api/duration-ranking`,
  `/api/leaderboard`).

30 + 20 = 50 concurrent requests against a server that can run **40** at once.

## Result: the read path is starved by agent calls

Starlette runs every `def` endpoint in an anyio threadpool with **exactly 40
tokens** (verified: `anyio.to_thread.current_default_thread_limiter()
.total_tokens == 40`). A `/ask` occupies one of those tokens for the entire
agent run.

Server-side snapshot from `GET /api/perf` immediately after the run
(`loadtest/results/baseline-perf.json`):

| route | calls | in_flight | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |
|---|---:|---:|---:|---:|---:|---:|
| `/api/runs/{id}/ask` | 359 | 1 | 64 792 | 141 010 | 144 528 | 148 286 |
| `/api/duration-ranking` | 189 | 0 | 2 | 110 604 | 110 622 | 110 625 |
| `/api/wallets/{address}/runs` | 191 | 0 | 3 | 42 685 | 42 717 | 119 857 |
| `/api/wallets` | 193 | 0 | 2 | 10 487 | 37 062 | 111 969 |
| `/api/leaderboard` | 177 | 0 | 2 | 5 478 | 84 169 | 110 786 |

k6 client-side digest for the same run:

```
READ PATH   avg=1622.7 ms   p95=8336.3 ms   max=56254.5 ms
total requests : 1091
failure rate   : 33.00%
thresholds on 'http_req_duration{scenario:readers}' CROSSED (p95 target < 500 ms)
```

### Reading the table

The read routes have a **p50 of 2–3 ms** but a **p95 of 42–110 seconds**. That
bimodality is the entire finding: the SQL is fast, it just can't get a thread.
When a thread is free, a read returns in single-digit milliseconds; when all 40
are held by agent calls, the *same query* waits up to nearly two minutes.

Two of three manual `GET /api/perf` probes issued right after the run came back
**empty** — the server had no free thread to answer the metrics request itself.
That is the clearest possible statement of the problem.

## Secondary findings

* **`/api/perf` is in the measured tail.** At peak, `in_flight` for
  `/api/runs/{id}/ask` hit **39 / 40** threadpool tokens.
* **Leak #1 (180s subprocess in the hot path) is currently dormant.**
  `POST /api/models/free` returns in **2.5 ms** — but only because the cached
  `free_{tool}.txt` files exist under a sibling repo bind-mounted at an
  absolute host path (`docker-compose.yml:30`,
  `/home/paf/Documents/code/misc/prompt-viewer/ask_jobs`). `ask.py:_read_free_file`
  returns `[]` for a missing *or empty* file, and `_generate_free_list` then
  shells out for up to **180 seconds**. Move or empty that directory and every
  `/ask` silently pays a 180-second tax, twice (`main.py:263` and again inside
  `is_free_model`). Fixing this is defensive, not speculative.
* **Connection pool.** `db.py` uses `SimpleConnectionPool(1, 10)` with no
  `maxwait`; exhaustion surfaces as a raw `PoolError` → HTTP 500. It did not
  trip in this run because only 10 threads reached the DB concurrently, but it
  is the next thing to break as concurrency rises.

## What "fixed" has to beat

| metric | baseline |
|---|---|
| read p95 under load | 8 336 ms (client) / up to 110 604 ms (server, worst route) |
| read failure rate | 33 % |
| `/ask` time-to-first-response | blocks for the full agent run (148 s observed) |
| threadpool tokens held by `/ask` | 39 / 40 |
| throughput of agent work | gated by thread occupancy, not by CPU |

The target: `/ask` returns **202 in single-digit milliseconds**, no request ever
owns a thread for its whole lifetime, and read p95 stays in the low tens of
milliseconds under the identical profile.

## Reproduce

```bash
make start
curl -s -X POST http://localhost:8002/api/perf/reset
mkdir -p loadtest/results
docker run --rm -i --network host \
  -v "$PWD/loadtest:/scripts" grafana/k6 run /scripts/k6.js
curl -s http://localhost:8002/api/perf | python3 -m json.tool
```