import { useState } from "react";
import { getPerf, resetPerf, type PerfRoute } from "./api";

function ms(v: number): string {
  if (v >= 1000) return (v / 1000).toFixed(2) + "s";
  return Math.round(v) + "ms";
}

/** Colour-code a p95 so the slow routes are obvious at a glance. */
function p95Cell(v: number) {
  const style =
    v >= 1000
      ? { color: "#f85149" }
      : v >= 200
        ? { color: "#d29922" }
        : { color: "#3fb950" };
  return <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>{ms(v)}</span>;
}

export default function PerfPage() {
  const [rows, setRows] = useState<PerfRoute[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const snap = await getPerf();
      setRows(snap.routes);
      setErr("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    await resetPerf();
    setRows([]);
  }

  return (
    <div className="card" style={{ display: "block" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 13 }}>
          API latency — worst p95 first
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} disabled={busy}>
            {busy ? "loading…" : "Refresh"}
          </button>
          <button onClick={reset}>Reset</button>
        </div>
      </div>

      {err && <p className="dim" style={{ marginTop: 12 }}>{err}</p>}

      {rows === null ? (
        <p className="dim" style={{ marginTop: 12 }}>
          Press Refresh after running the load test to populate this table.
        </p>
      ) : rows.length === 0 ? (
        <p className="dim" style={{ marginTop: 12 }}>
          No requests recorded yet. Run the k6 script, then Refresh.
        </p>
      ) : (
        <table style={{ width: "100%", marginTop: 12, fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--dim)" }}>
              <th>route</th>
              <th>calls</th>
              <th>inflight</th>
              <th>p50</th>
              <th>p95</th>
              <th>p99</th>
              <th>max</th>
              <th>errors</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.route} style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ fontFamily: "monospace" }}>{r.route}</td>
                <td>{r.count}</td>
                <td>{r.in_flight > 0 ? <span style={{ color: "#d29922" }}>{r.in_flight}</span> : 0}</td>
                <td>{ms(r.p50_ms)}</td>
                <td>{p95Cell(r.p95_ms)}</td>
                <td>{ms(r.p99_ms)}</td>
                <td>{ms(r.max_ms)}</td>
                <td>{r.errors > 0 ? <span style={{ color: "#f85149" }}>{r.errors}</span> : 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="dim" style={{ fontSize: 12, marginTop: 12 }}>
        Percentiles come from a rolling in-memory buffer (no external metrics
        server). <b>inflight</b> is the number of requests executing right now
        — during a load test it reveals the worker/thread ceiling.
      </p>
    </div>
  );
}