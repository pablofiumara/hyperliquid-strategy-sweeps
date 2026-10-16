import { useEffect, useRef, useState, type ReactNode } from "react";
import PerfPage from "./PerfPage";
import {
  askRun,
  genSummary,
  getConversations,
  getFreeModels,
  getDurationRanking,
  getJob,
  getRunByLabel,
  getRuns,
  getSummary,
  getWallets,
  rate,
  streamJob,
  type Conversation,
  type DurationRank,
  type FreeModel,
  type JobStatus,
  type Run,
  type RunDetail,
  type Wallet,
  type WalletSummary,
} from "./api";

type View =
  | { page: "wallets" }
  | { page: "runs"; wallet: string }
  | { page: "run"; wallet: string; label: string }
  | { page: "perf" };

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
    case "perf":
      return "/perf";
    case "runs":
      return `/wallet/${view.wallet}`;
    case "run":
      return `/wallet/${view.wallet}/${view.label}`;
  }
};

function viewFromPath(path: string): View {
  if (path === "/perf") return { page: "perf" };
  let m = path.match(/^\/wallet\/([^/]+)\/([^/]+)$/);
  if (m) return { page: "run", wallet: m[1], label: decodeURIComponent(m[2]) };
  m = path.match(/^\/wallet\/([^/]+)$/);
  if (m) return { page: "runs", wallet: m[1] };
  return { page: "wallets" };
}


/** Card that behaves like a link: left-click navigates in-app (SPA), while
    middle-click / right-click "open in new tab" works because it's a real
    <a href>. */
function CardLink({ href, onNav, children }: { href: string; onNav: () => void; children: ReactNode }) {
  return (
    <a
      className="card"
      href={href}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
        e.preventDefault();
        onNav();
      }}
    >
      {children}
    </a>
  );
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
      {view.page === "perf" && <PerfPage />}
      {view.page !== "run" && <BottomBar view={view} navigate={navigate} />}
    </div>
  );
}

function WalletList({ onOpen }: { onOpen: (a: string) => void }) {
  const [wallets, setWallets] = useState<Wallet[] | null>(null);
  const [err, setErr] = useState("");
  const [ranking, setRanking] = useState<DurationRank[] | null>(null);
  const [rankOpen, setRankOpen] = useState(false);
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
  useEffect(() => {
    getDurationRanking()
      .then((r) => setRanking(r))
      .catch(() => setRanking([]));
  }, []);
  if (err) return <p className="dim">{err}</p>;
  if (!wallets) return <p className="loading">loading…</p>;
  return (
    <>
      <div className="card" style={{ cursor: "default", display: "block", marginBottom: 16 }}>
        <div
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, cursor: "pointer" }}
          onClick={() => setRankOpen(!rankOpen)}
        >
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            Q: Which model takes longer to answer?
          </div>
          <span className="dim" style={{ fontSize: 12 }}>{rankOpen ? "▲ hide" : "▼ show"}</span>
        </div>
        {rankOpen && (
          <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            {ranking === null ? (
              <div className="dim" style={{ fontSize: 13 }}>loading…</div>
            ) : ranking.length === 0 ? (
              <div className="dim" style={{ fontSize: 13 }}>
                A: No timed answers yet — every stored answer's seconds are
                summed per model once models start answering.
              </div>
            ) : (
              <div style={{ fontSize: 13 }}>
                <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>
                  A: fastest → slowest, summed over every stored answer:
                </div>
                {ranking.map((r, i) => (
                  <div key={`${r.tool}/${r.model}`} style={{ marginTop: 4 }}>
                    <span className={i === 0 ? "score pos" : i === ranking.length - 1 ? "score neg" : "dim"}>
                      #{i + 1}
                    </span>{" "}
                    {r.label || r.model}
                    <span className="dim">
                      {" "}· total {Math.round(Number(r.total_s))}s · {r.runs} run{r.runs === 1 ? "" : "s"} · {r.wallets} wallet{r.wallets === 1 ? "" : "s"} · avg {Math.round(Number(r.avg_s))}s
                    </span>
                    <div className="dim mono" style={{ fontSize: 11 }}>{r.model}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      {wallets.map((w) => (
        <CardLink key={w.address} href={pathFor({ page: "runs", wallet: w.address })} onNav={() => onOpen(w.address)}>
          <span className="mono">{w.address}</span>
          <span className="dim">
            {w.runs} runs · {w.done} done
          </span>
        </CardLink>
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
  const generatingRef = useRef(false);
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
    if (generatingRef.current) return;
    generatingRef.current = true;
    setGenerating(true);
    setSumErr("");
    try {
      const s = await genSummary(wallet);
      setSummary(s);
    } catch (e) {
      setSumErr(String(e));
    } finally {
      generatingRef.current = false;
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
        <CardLink key={r.id} href={pathFor({ page: "run", wallet, label: r.label })} onNav={() => onOpen(r.label)}>
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
        </CardLink>
      ))}
    </>
  );
}

function RunPage({ wallet, label, onBack }: { wallet: string; label: string; onBack: () => void }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [err, setErr] = useState("");
  const [convos, setConvos] = useState<Conversation[] | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const askingRef = useRef(false);
  const [askErr, setAskErr] = useState("");
  const [freeModels, setFreeModels] = useState<FreeModel[]>([]);
  const [selected, setSelected] = useState<string>("");
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

  useEffect(() => {
    if (run?.id) {
      getConversations(run.id)
        .then((c) => setConvos(c))
        .catch(() => setConvos([]));
    }
  }, [run?.id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let i = 0; i < 3 && !cancelled; i++) {
        try {
          const m = await getFreeModels();
          if (cancelled) return;
          setFreeModels(m);
          setSelected((prev) => prev || (m.length ? m[0].name : prev));
          return;
        } catch {
          if (i < 2) await new Promise((r) => setTimeout(r, 1000));
        }
      }
          if (!cancelled) setFreeModels([]);
    })();
    return () => { cancelled = true; };
  }, []);

  const closeStreamRef = useRef<(() => void) | null>(null);
  const [askStatus, setAskStatus] = useState("");

  useEffect(() => () => closeStreamRef.current?.(), []);

  async function ask() {
    if (!run || !question.trim() || askingRef.current) return;
    askingRef.current = true;
    setAsking(true);
    setAskErr("");
    setAskStatus("queueing…");
    let poller: ReturnType<typeof setInterval> | null = null;
    try {
      const fm = freeModels.find((x) => x.name === selected);
      const accepted = await askRun(run.id, question.trim(), fm?.tool, fm?.model);
      setQuestion("");
      setAskStatus("agent thinking…");

      await new Promise<void>((resolve) => {
        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          closeStreamRef.current?.();
          closeStreamRef.current = null;
          if (poller) clearInterval(poller);
          resolve();
        };
        const onTerminal = (j: JobStatus) => {
          if (j.status === "done") {
            setAskStatus("");
            getConversations(run.id).then(setConvos).catch(() => {});
            finish();
          } else if (j.status === "error") {
            setAskErr(j.error || "agent failed");
            setAskStatus("");
            finish();
          } else if (j.status === "pending") {
            setAskStatus("queued…");
          } else {
            setAskStatus("agent thinking…");
          }
        };
        closeStreamRef.current = streamJob(accepted.job_id, onTerminal);
        // Safety net for when the SSE stream cannot be established.
        poller = setInterval(async () => {
          if (settled) return;
          try {
            onTerminal(await getJob(accepted.job_id));
          } catch {
            /* keep polling */
          }
        }, 2000);
      });
    } catch (e) {
      setAskStatus("");
      setAskErr(String(e));
    } finally {
      if (poller) clearInterval(poller);
      askingRef.current = false;
      setAsking(false);
    }
  }

  async function vote(value: -1 | 1) {
    if (!run) return;
    // Clicking the active rating again undoes it (resets to 0).
    const next: -1 | 0 | 1 = run.my_rating === value ? 0 : value;
    const res = await rate(run.id, next);
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
      {run.report ? (
        <pre className="report">{run.report}</pre>
      ) : (
        <p className="dim">No strategy report for this run.</p>
      )}
      {run.has_report ? (
        <div className="card" style={{ cursor: "default", marginTop: 12 }}>
          <div style={{ marginBottom: 8, fontWeight: 700 }}>💬 Ask about this report</div>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <select value={selected} onChange={(e) => setSelected(e.target.value)} style={{ minWidth: 260 }}>
              {freeModels.length ? (
                freeModels.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.tool}/{m.model} {m.price}
                  </option>
                ))
              ) : (
                <option value="">No free models</option>
              )}
            </select>
            <input
              style={{ flex: 1 }}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder="Ask a follow-up question…"
            />
            <button className="primary" onClick={ask} disabled={asking || !question.trim() || !selected}>
              {asking ? "Asking…" : "Ask"}
            </button>
          </div>
          {askStatus ? (
            <p className="dim" style={{ fontSize: 12, marginBottom: 8 }}>
              ⟳ {askStatus} (the agent can take up to 5 minutes)
            </p>
          ) : null}
          {askErr ? <p className="dim">{askErr}</p> : null}
          {(convos || []).map((c) => (
            <div key={c.id} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600 }}>Q: {c.question}</div>
              <pre className="report" style={{ marginTop: 4 }}>{c.answer}</pre>
            </div>
          ))}
        </div>
      ) : null}
      <FixedRatingBar run={run} onVote={vote} onBack={onBack} />
    </>
  );
}

/** Fixed bottom bar on the run page: rating buttons always reachable, even
   halfway down a long strategy report. */
function FixedRatingBar({
  run,
  onVote,
  onBack,
}: {
  run: RunDetail;
  onVote: (v: -1 | 1) => void;
  onBack: () => void;
}) {
  return (
    <div className="bottombar">
      <button onClick={onBack}>← {run.label}</button>
      <button
        className={run.my_rating === 1 ? "primary" : ""}
        onClick={() => onVote(1)}
      >
        👍 Interesting
      </button>
      <button
        className={run.my_rating === -1 ? "primary" : ""}
        onClick={() => onVote(-1)}
      >
        👎 Not interesting
      </button>
      <span className="dim" style={{ alignSelf: "center" }}>
        +{run.global_score}
      </span>
    </div>
  );
}

/** Fixed bottom bar: always reachable, even deep in a long list. */
function BottomBar({ view, navigate }: { view: View; navigate: (v: View) => void }) {
  if (view.page === "perf") {
    return (
      <div className="bottombar">
        <button onClick={() => navigate({ page: "wallets" })}>← Wallets</button>
        <button className="primary" disabled>
          ⚡ perf
        </button>
      </div>
    );
  }
  if (view.page === "wallets") {
    return (
      <div className="bottombar">
        <button className="primary" disabled>
          ⛓ wallets
        </button>
        <button onClick={() => navigate({ page: "perf" })}>⚡ perf</button>
      </div>
    );
  }
  // runs view
  return (
    <div className="bottombar">
      <button onClick={() => navigate({ page: "wallets" })}>← Wallets</button>
      <button className="primary">
        {view.wallet.slice(0, 12)}…{view.wallet.slice(-4)}
      </button>
    </div>
  );
}
