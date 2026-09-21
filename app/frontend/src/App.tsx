import { useEffect, useRef, useState } from "react";
import {
  genSummary,
  getRunByLabel,
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
  | { page: "run"; wallet: string; label: string };

const POLL_MS = 5000;

/** Remember where the user scrolled in a view and restore it when they
   come back -- so clicking a model and returning doesn't dump them back
   at the top of a long list. */
function useRestoreScroll(key: string, ready: boolean = true) {
  useEffect(() => {
    if (!ready) return;
    const store = `scroll:${key}`;
    // Keep the latest scroll position so it's always available on unmount,
    // even if window.scrollY has already been reset to 0 (e.g. the new page
    // is shorter and the browser fired a scroll event during navigation).
    let y = window.scrollY;
    let ticking = false;
    const flush = () => { if (y > 0) sessionStorage.setItem(store, String(y)); };
    const onScroll = () => {
      y = window.scrollY;
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(() => { ticking = false; flush(); });
      }
    };
    const raf = requestAnimationFrame(() => {
      const v = Number(sessionStorage.getItem(store) || 0);
      if (v > 0) window.scrollTo(0, v);
    });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("beforeunload", flush);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("beforeunload", flush);
      flush();
    };
  }, [key, ready]);
}

/** Format a model's context window as a short human string (e.g. 262144 -> "256k"). */
function fmtCtx(n: number | null | undefined): string {
  if (!n || n <= 0) return "—";
  if (n >= 1048576) return `${(n / 1048576).toFixed(n % 1048576 === 0 ? 0 : 1)}M`;
  if (n >= 1024) return `${Math.round(n / 1024)}k`;
  return String(n);
}

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
      return `/wallet/${view.wallet}`;
    case "run":
      return `/wallet/${view.wallet}/${view.label}`;
  }
};

function viewFromPath(path: string): View {
  let m = path.match(/^\/wallet\/([^/]+)\/([^/]+)$/);
  if (m) return { page: "run", wallet: m[1], label: decodeURIComponent(m[2]) };
  m = path.match(/^\/wallet\/([^/]+)$/);
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
          onOpen={(label) => navigate({ page: "run", wallet: view.wallet, label })}
          onBack={() => navigate({ page: "wallets" })}
        />
      )}
      {view.page === "run" && (
        <RunPage
          key={view.label}
          wallet={view.wallet}
          label={view.label}
          onBack={() => navigate({ page: "runs", wallet: view.wallet })}
        />
      )}
      <BottomBar view={view} navigate={navigate} />
    </div>
  );
}

function WalletList({ onOpen }: { onOpen: (a: string) => void }) {
  const [wallets, setWallets] = useState<Wallet[] | null>(null);
  const [err, setErr] = useState("");
  useRestoreScroll("wallets");
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
  onOpen: (label: string) => void;
  onBack: () => void;
}) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [err, setErr] = useState("");
  const [summary, setSummary] = useState<WalletSummary | null | undefined>(undefined);
  const [sumErr, setSumErr] = useState("");
  const [generating, setGenerating] = useState(false);
  const scrollKey = `runs:${wallet}`;
  useRestoreScroll(scrollKey, !!runs);
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
        <div key={r.id} className="card" onClick={() => onOpen(r.label)}>
          <div>
            <div>{r.label}</div>
            <div className="dim" style={{ fontSize: 12 }}>
              {r.model} {r.variant ? `· ${r.variant}` : ""} · {r.duration_s ?? "?"}s
              {" · ctx " + fmtCtx(r.context_size)}
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span className={`score ${r.global_score > 0 ? "pos" : r.global_score < 0 ? "neg" : ""}`}>
              {r.global_score > 0 ? "+" : ""}
              {r.global_score}
            </span>
            <span className={`pill ${r.display_status}`}>{r.display_status}</span>
          </div>
        </div>
      ))}
    </>
  );
}

function RunPage({ wallet, label, onBack }: { wallet: string; label: string; onBack: () => void }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [err, setErr] = useState("");
  usePoll(() => {
    getRunByLabel(wallet, label)
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
    const res = await rate(run.id, value);
    const fresh = await getRunByLabel(wallet, label);
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
            {run.model} · {run.display_status} · probe {run.probe} · {run.duration_s}s
            {" · ctx " + fmtCtx(run.context_size)}
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

/** Fixed bottom bar: always reachable, even deep in a long model list. */
function BottomBar({ view, navigate }: { view: View; navigate: (v: View) => void }) {
  const toWallets = () => navigate({ page: "wallets" });

  if (view.page === "wallets") {
    return (
      <div className="bottombar">
        <button className="primary" disabled>
          ⛓ wallets
        </button>
      </div>
    );
  }
  return (
    <div className="bottombar">
      <button onClick={toWallets}>← Wallets</button>
      {view.page === "run" && (
        <button className="primary" onClick={() => navigate({ page: "runs", wallet: view.wallet })}>
          ← {view.label}
        </button>
      )}
    </div>
  );
}
