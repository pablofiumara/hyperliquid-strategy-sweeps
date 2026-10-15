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

export async function askRun(runId: number, question: string, tool?: string | null, model?: string | null) {
  const res = await fetch(`/api/runs/${runId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client": "ui" },
    body: JSON.stringify({ question, tool: tool || null, model: model || null }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as { answer: string; tool?: string; model: string; citations: number[] };
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
export const getRuns = (addr: string) =>
  api<Run[]>(`/api/wallets/${addr}/runs`);
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
