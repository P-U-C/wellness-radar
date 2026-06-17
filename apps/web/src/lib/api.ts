export type SourceRef = {
  source_name: string;
  url: string | null;
  trust_tier: string;
  seen_at: string;
  source_record_id: string | null;
  licence: string | null;
};

export type Operator = {
  id: string;
  name: string;
  categories: string[];
  status: string;
  address: string | null;
  municipality: string | null;
  neighborhood: string | null;
  lat: number;
  lng: number;
  confidence_score: number;
  source_refs: SourceRef[];
  licence_ref?: string;
  signals?: Signal[];
};

export type Signal = {
  id: string;
  type: string;
  severity: string;
  title: string;
  summary: string | null;
  why_it_matters: string | null;
  source_name: string;
  source_url: string | null;
  trust_tier: string;
  occurred_at: string;
  lat: number | null;
  lng: number | null;
  related_operator_id: string | null;
  confidence_score: number;
  source_refs: SourceRef[];
};

export type SourceRun = {
  id: number;
  source_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  records_fetched: number;
  records_persisted: number;
  records_rejected: number;
  error_count: number;
  error_message: string | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export async function fetchOperators(category?: string): Promise<Operator[]> {
  const params = new URLSearchParams({ bbox: "-123.3,49.0,-122.5,49.4" });
  if (category && category !== "all") {
    params.set("category", category);
  }
  const data = await getJson<{ items: Operator[] }>(`/operators?${params.toString()}`);
  return data.items;
}

export async function fetchSignals(operatorId?: string): Promise<Signal[]> {
  const params = new URLSearchParams({ bbox: "-123.3,49.0,-122.5,49.4" });
  if (operatorId) {
    params.set("related_operator_id", operatorId);
  }
  const data = await getJson<{ items: Signal[] }>(`/signals?${params.toString()}`);
  return data.items;
}

export async function fetchSourceRuns(): Promise<SourceRun[]> {
  const data = await getJson<{ items: SourceRun[] }>("/admin/source-runs?limit=5");
  return data.items;
}
