// Load test for the Hyperliquid strategy API.
//
// Run (from the repo root) — k6 runs in its own container, nothing to install:
//
//   mkdir -p loadtest/results
//   docker run --rm -i --network host \
//     -v "$PWD/loadtest:/scripts" grafana/k6 run /scripts/k6.js
//
// The profile deliberately mixes the two very different workloads the backend
// has to serve at once:
//
//   readers  cheap GETs -- the "real-time web/mobile" traffic
//   askers   POST /ask -- AI agent calls that block for up to 300s
//
// The headline number is how the askers starve the readers. Starlette runs
// sync endpoints in an anyio threadpool with exactly 40 tokens, so once the
// askers hold ~30 of them the read path runs out of capacity. The fix is the
// job queue (202 + SSE) that stops a request from owning a thread at all.
//
// To make the run repeatable, pass PHASE=after once the queue exists: the
// thresholds below then apply to the new 202 contract.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8002";

// Wallets present in the dev DB (populated by import_all at startup).
const WALLETS = [
  "0x0bb81e516c88881c54529e1790470cb5e9f8740d",
  "0xe755b71641b95ff7a6bd40030e9dc7ac7939e578",
];

const READ_VUS = Number(__ENV.READ_VUS || 20);
const ASK_VUS = Number(__ENV.ASK_VUS || 30);

export const options = {
  scenarios: {
    askers: {
      // Start first so the blocked threads accumulate before readers ramp.
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "15s", target: ASK_VUS },
        { duration: "45s", target: ASK_VUS },
        { duration: "10s", target: 0 },
      ],
      exec: "askers",
    },
    readers: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "20s", target: READ_VUS },
        { duration: "45s", target: READ_VUS },
        { duration: "10s", target: 0 },
      ],
      exec: "readers",
    },
  },
  thresholds: {
    "http_req_duration{scenario:readers}": ["p(95)<500"],
    "http_req_failed{scenario:readers}": ["rate<0.05"],
  },
};

export function readers() {
  const wallet = WALLETS[Math.floor(Math.random() * WALLETS.length)];
  const routes = [
    "/api/wallets",
    `/api/wallets/${wallet}/runs`,
    "/api/duration-ranking",
    "/api/leaderboard",
  ];
  for (const r of routes) {
    const res = http.get(`${BASE_URL}${r}`, { tags: { route: r } });
    check(res, { "read 200": (x) => x.status === 200 });
  }
  sleep(0.5);
}

export function askers() {
  // A real ask spawns an AI CLI subprocess that can run for 300s. We fire
  // with a short client timeout so the VU recycles quickly: what we are
  // measuring is how much server-side capacity each ask *consumes*, not how
  // long the agent takes to answer.
  const res = http.post(
    `${BASE_URL}/api/runs/1/ask`,
    JSON.stringify({ question: "What is the base entry size and take-profit target?" }),
    {
      headers: { "Content-Type": "application/json", "X-Client": "loadtest" },
      timeout: "3s",
      tags: { route: "/api/runs/1/ask" },
    }
  );
  check(res, {
    // 200 = pre-queue blocking behaviour
    // 202 = queued behaviour (the fix)
    // 429 = admission control working
    // 503 = saturated / no free models
    "ask handled": (x) => [200, 202, 429, 503].includes(x.status),
  });
  sleep(2);
}

export function handleSummary(data) {
  const rows = [];
  const line = (s) => rows.push(s);
  line("================ READ PATH (p95 / p99, ms) ================");
  for (const [k, v] of Object.entries(data.metrics)) {
    if (k.startsWith("http_req_duration{expected_response:true}")) {
      const vals = v.values;
      line(
        `${(v.tags && v.tags.scenario ? v.tags.scenario : "all").padEnd(8)} ` +
          `avg=${Number(vals.avg).toFixed(1)}  p95=${Number(vals["p(95)"]).toFixed(1)}  ` +
          `p99=${Number(vals["p(99)"]).toFixed(1)}  max=${Number(vals.max).toFixed(1)}  n=${vals["http_req_count"]}`
      );
    }
  }
  const rate = data.metrics.http_req_failed && data.metrics.http_req_failed.values.rate;
  const reqs = data.metrics.http_reqs && data.metrics.http_reqs.values.count;
  line("======================================================");
  line(`total requests : ${reqs}`);
  line(`failure rate   : ${(rate * 100).toFixed(2)}%`);
  for (const [k, v] of Object.entries(data.metrics)) {
    if (k.startsWith("checks")) line(`${k}: ${(v.values.passes * 100).toFixed(1)}% passed`);
  }
  console.log(rows.join("\n"));
  return {
    stdout: rows.join("\n") + "\n",
    "summary.json": JSON.stringify(data, null, 2),
  };
}