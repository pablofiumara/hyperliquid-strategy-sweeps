import { useEffect, useRef, useState } from "react";
import {
  genSummary,
  getRun,
  getRuns,
  getSummary,
  getWallets,
  rate,
  type Run,
  type RunDetail,
  type Wallet,
  type WalletSummary,
} from "./api";

type View =
  | { page: "wallets" }
  | { page: "runs"; wallet: string }
  | { page: "run"; wallet: string; runId: number };

const POLL_MS = 5000;

/** Run `fn` immediately, then every `ms`; also when the tab regains focus. */
function usePoll(fn: () => void, ms: number = POLL_MS) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    const tick = () => ref.current();
    tick();
    const t = window.setInterval(tick, ms);
    const onVis = () => {
      if (!document.hidden) tick();
    };
    window.addEventListener("focus", onVis);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(t);
      window.removeEventListener("focus", onVis);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [ms]);
}

/** Auto-reload the tab when a new frontend build is deployed. */
function useBuildWatcher() {
  useEffect(() => {
    const boot = document.querySelector<HTMLScriptElement>('script[type="module"]')?.src ?? "";
    const t = window.setInterval(async () => {
      try {
        const html = await (await fetch("/index.html", { cache: "no-store" })).text();
        const asset = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/);
        if (asset && boot && !boot.includes(asset[0])) window.location.reload();
      } catch {
        /* transient — retry next tick */
      }
    }, 30000);
    return () => window.clearInterval(t);
  }, []);
}

// ------------------- URL routing (sync in-app view with browser history) ---
// One fact, one place: the URL encodes the view, so the browser Back/Forward
// buttons and bookmarks deep-link correctly (wallets <-> models <-> run).
const pathFor = (view: View): string => {
  switch (view.page) {
    case "wallets":
      return "/";
    case "runs":
      return `/w/${view.wallet}`;
    case "run":
      return `/w/${view.wallet}/run/${view.runId}`;
  }
};

function viewFromPath(path: string): View {
  let m = path.match(/^\/w\/([^/]+)\/run\/(\d+)$/);
  if (m) return { page: "run", wallet: m[1], runId: Number(m[2]) };
  m = path.match(/^\/w\/([^/]+)$/);
  if (m) return { page: "runs", wallet: m[1] };
  return { page: "wallets" };
}


export default function App() {
  const [view, setView] = useState<View>(() => viewFromPath(location.pathname));
  useBuildWatcher();

  const navigate = (v: View) => {
    const p = pathFor(v);
    if (location.pathname !== p) history.pushState(null, "", p);
    setView(v);
  };
  useEffect(() => {
    const onPop = () => setView(viewFromPath(location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  return (
    <div className="container">
      <h1>
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate({ page: "wallets" });
          }}
        >
          ⛓ Hyperliquid Strategy Sweep
        </a>
      </h1>
      {view.page === "wallets" && <WalletList onOpen={(address) => navigate({ page: "runs", wallet: address })} />}
      {view.page === "runs" && (
        <RunList
          key={view.wallet}
          wallet={view.wallet}
          onOpen={(runId) => navigate({ page: "run", wallet: view.wallet, runId })}
          onBack={() => navigate({ page: "wallets" })}
        />
      )}
      {view.page === "run" && (
        <RunPage
          key={view.runId}
          runId={view.runId}
          onBack={() => navigate({ page: "runs", wallet: view.wallet })}
        />
      )}
    </div>
  );
}

function WalletList({ onOpen }: { onOpen: (a: string) => void }) {
  const [wallets, setWallets] = useState<Wallet[] | null>(null);
  const [err, setErr] = useState("");
  usePoll(() => {
    getWallets()
      .then((w) => {
        setWallets(w);
        setErr("");
      })
      .catch((e) => {
        if (!wallets) setErr(String(e));
      });
  }, 10000);
  if (err) return <p className="dim">{err}</p>;
  if (!wallets) return <p className="loading">loading…</p>;
  return (
    <>
      {wallets.map((w) => (
        <div key={w.address} className="card" onClick={() => onOpen(w.address)}>
          <span className="mono">{w.address}</span>
          <span className="dim">
            {w.runs} runs · {w.done} done
          </span>
        </div>
      ))}
    </>
  );
}

function RunList({
  wallet,
  onOpen,
  onBack,
}: {
  wallet: string;
  onOpen: (id: number) => void;
  onBack: () => void;
}) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [err, setErr] = useState("");
  const [summary, setSummary] = useState<WalletSummary | null | undefined>(undefined);
  const [sumErr, setSumErr] = useState("");
  const [generating, setGenerating] = useState(false);
  usePoll(() => {
    getRuns(wallet)
      .then((r) => {
        setRuns(r);
        setErr("");
      })
      .catch((e) => {
        if (!runs) setErr(String(e));
      });
    getSummary(wallet)
      .then((s) => {
        setSummary(s);
        setSumErr("");
      })
      .catch((e) => {
        if (summary === undefined) setSumErr(String(e));
      });
  });
  if (err) return <p className="dim">{err}</p>;
  if (!runs) return <p className="loading">loading…</p>;

  async function onGenerate() {
    setGenerating(true);
    setSumErr("");
    try {
      const s = await genSummary(wallet);
      setSummary(s);
    } catch (e) {
      setSumErr(String(e));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <>
      <p className="dim mono" style={{ cursor: "pointer" }} onClick={onBack}>
        ← {wallet}
      </p>
      <div className="card" style={{ cursor: "default" }}>
        <div style={{ flex: 1 }}>
          <div>
            🧠 Wallet summary{" "}
            <span className="dim" style={{ fontSize: 12 }}>
              {summary === undefined
                ? "loading…"
                : summary
                  ? `· ${summary.strategy_report_count}/${summary.model_count} strategy reports · ${summary.confidence} confidence · ${summary.generated_by}`
                  : "· none yet"}
            </span>
          </div>
          {summary === undefined ? (
            <p className="dim" style={{ fontSize: 13 }}>loading…</p>
          ) : summary ? (
            <>
              <p style={{ fontSize: 14 }}>{summary.consensus_strategy}</p>
              {summary.key_params ? (
                <p className="dim" style={{ fontSize: 12 }}>{summary.key_params}</p>
              ) : null}
              {summary.disagreements?.length ? (
                <div className="dim" style={{ fontSize: 12 }}>
                  ⚠ disagreements:
                  <ul>
                    {(summary.disagreements ?? []).map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="dim" style={{ fontSize: 12 }}>no disagreements — models agree.</p>
              )}
              {summary.trade_example ? (
                <div className="card" style={{ marginTop: 14, background: "#0a1a12", border: "1px solid #1f5d3a" }}>
                  <div style={{ fontSize: 11, textTransform: "uppercase", color: "#5dd39e", marginBottom: 6, fontWeight: 700 }}>
                    📌 Trade Example (copy this)
                  </div>
                  <p style={{ fontSize: 14, lineHeight: 1.55 }}>{summary.trade_example}</p>
                </div>
              ) : null}
            </>
          ) : (
            <>
              <p className="dim" style={{ fontSize: 13 }}>
                No summary yet — generate one with the local free LLM{sumErr ? `: ${sumErr}` : "."}
              </p>
              <button disabled={generating} onClick={onGenerate}>
                {generating ? "Generating… (~30s)" : "Generate summary"}
              </button>
            </>
          )}
        </div>
      </div>
      {runs.map((r) => (
        <div key={r.id} className="card" onClick={() => onOpen(r.id)}>
          <div>
            <div>{r.label}</div>
            <div className="dim" style={{ fontSize: 12 }}>
              {r.model} {r.variant ? `· ${r.variant}` : ""} · {r.duration_s ?? "?"}s
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span className={`score ${r.global_score > 0 ? "pos" : r.global_score < 0 ? "neg" : ""}`}>
              {r.global_score > 0 ? "+" : ""}
              {r.global_score}
            </span>
            <span className={`pill ${r.status}`}>{r.status}</span>
          </div>
        </div>
      ))}
    </>
  );
}

function RunPage({ runId, onBack }: { runId: number; onBack: () => void }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [err, setErr] = useState("");
  usePoll(() => {
    getRun(runId)
      .then((r) => {
        setRun(r);
        setErr("");
      })
      .catch((e) => {
        if (!run) setErr(String(e));
      });
  }, 10000);

  async function vote(value: -1 | 1) {
    if (!run || run.my_rating === value) return; // already rated this way
    const res = await rate(runId, value);
    const fresh = await getRun(runId);
    setRun({ ...fresh, global_score: res.model_global_score });
  }

  if (err) return <p className="dim">{err}</p>;
  if (!run) return <p className="loading">loading…</p>;
  return (
    <>
      <p className="dim mono" style={{ cursor: "pointer" }} onClick={onBack}>
        ← back to models
      </p>
      <div className="card" style={{ cursor: "default" }}>
        <div>
          <div>{run.label}</div>
          <div className="dim" style={{ fontSize: 12 }}>
            {run.model} · {run.status} · probe {run.probe} · {run.duration_s}s
          </div>
        </div>
        <span
          className={`score ${run.global_score > 0 ? "pos" : run.global_score < 0 ? "neg" : ""}`}
        >
          {run.global_score > 0 ? "+" : ""}
          {run.global_score}
        </span>
      </div>
      <div className="rater">
        <button
          className={run.my_rating === 1 ? "active-pos" : ""}
          onClick={() => vote(1)}
        >
          👍 Interesting
        </button>
        <button
          className={run.my_rating === -1 ? "active-neg" : ""}
          onClick={() => vote(-1)}
        >
          👎 Not interesting
        </button>
        <span className="dim" style={{ alignSelf: "center" }}>
          model score across all wallets: {run.global_score > 0 ? "+" : ""}
          {run.global_score}
        </span>
      </div>
      {run.report ? (
        <pre className="report">{run.report}</pre>
      ) : (
        <p className="dim">No strategy report for this run.</p>
      )}
    </>
  );
}
