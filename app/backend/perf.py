"""In-process request timing for every /api route.

Deliberately dependency-free (no prometheus client, no extra container): we
only need a rolling latency picture to prove the optimisation work, and that
has to survive being readable from our own React Performance tab.

Design notes:
  * ASGI middleware, not a FastAPI decorator, so it catches requests that
    404 and every route uniformly without touching handler signatures.
  * Route templates are normalised to the *pattern* (`/api/runs/{run_id}`)
    rather than raw paths, otherwise 60 runs produce 60 buckets and the
    percentiles are meaningless.
  * A fixed-size ring buffer per route keeps memory flat under sustained
    load. We store raw samples rather than a sketch because the buffer is
    small and exact percentiles are easier to explain in an interview.
  * A request that is still in flight when /api/perf is scraped cannot be
    reported (it has no duration yet); in-flight count is exposed separately
    so the threadpool ceiling is visible while the load test is running.
"""

from __future__ import annotations

import re
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware

# Per-route sample buffer. 2000 samples keeps p95 trustworthy under the
# load-test profile while costing ~16KB per hot route.
_MAX_SAMPLES = 2000
_WINDOW_SECONDS = 900.0

# Paths we never want to record: the perf endpoint would otherwise pollute
# its own numbers, and static/asset traffic is served by nginx anyway.
_SKIP_PREFIXES = ("/api/perf", "/docs", "/redoc", "/openapi.json", "/assets")


def normalise_path(path: str) -> str:
    """Collapse concrete ids back into the route template.

    /api/runs/42/ask -> /api/runs/{run_id}/ask
    /api/wallets/0xabc.../runs -> /api/wallets/{address}/runs
    """
    if not path.startswith("/api/"):
        return path
    out: list[str] = []
    for seg in path.split("/"):
        if not seg:
            continue
        if seg.isdigit():
            out.append("{id}")
        elif re.fullmatch(r"0x[0-9a-fA-F]{8,}", seg):
            out.append("{address}")
        else:
            out.append(seg)
    return "/" + "/".join(out)


class _RouteStats:
    __slots__ = ("samples", "count", "errors", "max_ms", "in_flight", "started")

    def __init__(self) -> None:
        self.samples: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self.count = 0
        self.errors = 0
        self.max_ms = 0.0
        self.in_flight = 0
        self.started = time.monotonic()

    def record(self, ms: float, failed: bool) -> None:
        self.samples.append(ms)
        self.count += 1
        if failed:
            self.errors += 1
        if ms > self.max_ms:
            self.max_ms = ms

    def percentile(self, pct: float) -> float:
        """Exact percentile over the retained samples (nearest-rank)."""
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = min(len(ordered) - 1, max(0, int(round(pct / 100.0 * len(ordered))) - 1))
        return round(ordered[idx], 2)

    def snapshot(self) -> dict:
        recent = [s for s in self.samples if s >= 0]
        return {
            "count": self.count,
            "errors": self.errors,
            "in_flight": self.in_flight,
            "p50_ms": self.percentile(50),
            "p95_ms": self.percentile(95),
            "p99_ms": self.percentile(99),
            "max_ms": round(self.max_ms, 2),
            "avg_ms": round(sum(recent) / len(recent), 2) if recent else 0.0,
            "uptime_s": round(time.monotonic() - self.started, 1),
        }


class PerfMiddleware(BaseHTTPMiddleware):
    """Times every request and buckets it by normalised route."""

    def __init__(self, app, stats: dict[str, _RouteStats] | None = None) -> None:
        super().__init__(app)
        self.stats: dict[str, _RouteStats] = stats if stats is not None else {}

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith(_SKIP_PREFIXES):
            return await call_next(request)

        key = normalise_path(path)
        entry = self.stats.get(key)
        if entry is None:
            entry = self.stats.setdefault(key, _RouteStats())
        entry.in_flight += 1
        started = time.perf_counter()
        failed = False
        try:
            response = await call_next(request)
            failed = response.status_code >= 500
            return response
        except Exception:
            failed = True
            raise
        finally:
            entry.in_flight -= 1
            ms = (time.perf_counter() - started) * 1000.0
            entry.record(ms, failed)


def install(app, stats: dict[str, _RouteStats] | None = None):
    """Attach the middleware and return the shared stats dict.

    Returning the dict lets main.py expose a reset/snapshot helper without
    reaching into app internals, and keeps the dict shared if the middleware
    is ever wrapped more than once.
    """
    if stats is None:
        stats = {}
    app.add_middleware(PerfMiddleware, stats=stats)
    return stats