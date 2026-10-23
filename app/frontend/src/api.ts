export type Wallet = { address: string; runs: number; done: number };
export type Run = {
  id: number;
  label: string;
  tool: string | null;
  model: string | null;
  variant: string | null;
  status: string;
  display_status: string;
  duration_s: number | null;
  my_rating: number;
  global_score: number;
  context_size: number | null;
  has_report: boolean;
};
export type RunDetail = Run & {
  probe: string | null;
  report: string | null;
  my_rating: number;
};

export type Conversation = {
  id: number;
  question: string;
  answer: string;
  model: string | null;
  citations: number[] | null;
  created_at: string;
};

export async function getConversations(runId: number) {
  return api<Conversation[]>(`/api/runs/${runId}/conversations`);
}

export type AskAccepted = {
  job_id: number;
  status: string;
  poll_url: string;
  stream_url: string;
};

/** POST an ask. The server answers 202 immediately and does the work in the
 *  background -- an agent can take up to 300s, so we must not wait inline. */
export async function askRun(
  runId: number,
  question: string,
  tool?: string | null,
  model?: string | null,
): Promise<AskAccepted> {
  const res = await fetch(`/api/runs/${runId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client": "ui" },
    body: JSON.stringify({ question, tool: tool || null, model: model || null }),
  });
  if (!res.ok) {
    // Surface the structured error envelope when the server provides one.
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.error?.message) detail = body.error.message;
    } catch {
      /* keep the status line */
    }
    throw new Error(detail);
  }
  return (await res.json()) as AskAccepted;
}

export type JobStatus = {
  job_id: number;
  status: "pending" | "running" | "done" | "error" | "cancelled";
  tool: string;
  model: string;
  answer?: string;
  citations?: number[] | null;
  error?: string;
};

/** Connect to a job over WebSocket. Returns a handle with send/close. */
export function connectJobSocket(
  jobId: number,
  handlers: {
    onJob?: (j: JobStatus) => void;
    onPresence?: (viewers: number) => void;
    onClose?: () => void;
  },
): { send: (msg: any) => void; close: () => void } {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws/jobs/${jobId}`);
  ws.onmessage = (e) => {
    try {
      const m = JSON.parse(e.data);
      if (m.type === "job" && m.job) handlers.onJob?.(m.job as JobStatus);
      else if (m.type === "presence") handlers.onPresence?.(m.viewers ?? 0);
    } catch {
      /* ignore */
    }
  };
  ws.onclose = () => handlers.onClose?.();
  return {
    send: (msg) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
    },
    close: () => ws.close(),
  };
}

export const getJob = (jobId: number) => api<JobStatus>(`/api/jobs/${jobId}`);

/** Follow a job to completion over SSE, reporting each state change.
 *  Falls back silently to nothing if the stream cannot be opened; callers
 *  should poll getJob as a safety net. */
export function streamJob(
  jobId: number,
  onUpdate: (j: JobStatus) => void,
): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  const handle = (e: MessageEvent) => {
    try {
      onUpdate(JSON.parse(e.data) as JobStatus);
    } catch {
      /* ignore malformed frame */
    }
  };
  for (const ev of ["pending", "running", "done", "error"]) {
    es.addEventListener(ev, handle as EventListener);
  }
  es.onmessage = handle;
  return () => es.close();
}

export type FreeModel = { tool: string; model: string; name: string; free: boolean; price: string };
export async function getFreeModels() {
  return api<FreeModel[]>("/api/models/free");
}

async function api<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const getWallets = () => api<Wallet[]>("/api/wallets");
export type PerfRoute = {
  route: string;
  count: number;
  errors: number;
  in_flight: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  avg_ms: number;
  uptime_s: number;
};
export type PerfSnapshot = { routes: PerfRoute[]; window_samples: number };

export type SlowQuery = {
  calls: number;
  total_ms: number;
  mean_ms: number;
  max_ms: number;
  rows: number;
  query: string;
};

export const getSlowQueries = (limit = 10) =>
  api<SlowQuery[]>(`/api/perf/queries?limit=${limit}`);

export async function getPerf(): Promise<PerfSnapshot> {
  return api<PerfSnapshot>("/api/perf");
}

export async function resetPerf() {
  const res = await fetch("/api/perf/reset", { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<{ ok: boolean }>;
}

export async function getRuns(addr: string) {
  return api<Run[]>(`/api/wallets/${addr}/runs`);
}
export type WalletSummary = {
  wallet: string;
  consensus_strategy: string;
  key_params: string;
  disagreements: string[];
  model_count: number;
  strategy_report_count: number;
  no_strategy_count: number;
  confidence: string;
  generated_by: string;
  generated_at: string;
trade_example: string;
};

export const getSummary = (addr: string) =>
  api<WalletSummary | null>(`/api/wallets/${addr}/summary`);

export async function genSummary(addr: string) {
  const res = await fetch(`/api/wallets/${addr}/summary`, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<WalletSummary>;
}

export type DurationRank = {
  tool: string | null;
  model: string | null;
  label: string | null;
  runs: number;
  wallets: number;
  total_s: number;
  avg_s: number;
};
export const getDurationRanking = () => api<DurationRank[]>("/api/duration-ranking");

export const getRunByLabel = (wallet: string, label: string) =>
  api<RunDetail>(`/api/wallets/${encodeURIComponent(wallet)}/runs/${encodeURIComponent(label)}`);

export async function rate(runId: number, value: -1 | 0 | 1) {
  const res = await fetch(`/api/runs/${runId}/rating`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<{ model_global_score: number }>;
}
