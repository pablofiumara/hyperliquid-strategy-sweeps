export type Wallet = { address: string; runs: number; done: number };
export type Run = {
  id: number;
  label: string;
  tool: string | null;
  model: string | null;
  variant: string | null;
  status: string;
  duration_s: number | null;
  my_rating: number;
  global_score: number;
  has_report: boolean;
};
export type RunDetail = Run & {
  probe: string | null;
  report: string | null;
  my_rating: number;
};

async function api<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const getWallets = () => api<Wallet[]>("/api/wallets");
export const getRuns = (addr: string) =>
  api<Run[]>(`/api/wallets/${addr}/runs`);
export const getRun = (id: number) => api<RunDetail>(`/api/runs/${id}`);

export async function rate(runId: number, value: -1 | 1) {
  const res = await fetch(`/api/runs/${runId}/rating`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<{ model_global_score: number }>;
}
