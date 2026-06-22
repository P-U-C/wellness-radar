export type SourceRef = {
  source_name: string;
  url: string | null;
  trust_tier: string;
  seen_at: string;
  source_record_id: string | null;
  licence: string | null;
};

export type ContactMethod = {
  type: "phone" | "email" | "website" | "social";
  value: string;
  platform?: string | null;
  source_ref: SourceRef;
  confidence: number;
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
  phone?: string | null;
  website?: string | null;
  social_links?: Record<string, string>;
  contacts: ContactMethod[];
  organization_id?: string | null;
  orgbook_id?: string | null;
  confidence_score: number;
  source_refs: SourceRef[];
  licence_ref?: string;
  signals?: Signal[];
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
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
  related_organization_id?: string | null;
  confidence_score: number;
  ai_generated_fields?: string[];
  prompt_version?: string | null;
  ai_model?: string | null;
  ai_category_suggestions?: string[];
  ai_severity_suggestion?: string | null;
  ai_confidence_score?: number | null;
  source_refs: SourceRef[];
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
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

export type SourceFreshness = {
  source_name: string;
  family: string;
  cadence: string;
  trust_tier: string;
  enabled: boolean;
  latest_run_id: number | null;
  latest_status: string | null;
  started_at: string | null;
  completed_at: string | null;
  records_fetched: number | null;
  records_persisted: number | null;
  records_rejected: number | null;
  error_count: number | null;
  error_message: string | null;
  rejected_count: number;
  sla_hours: number;
  age_hours: number | null;
  is_stale: boolean;
};

export type Person = {
  id: string;
  name: string;
  roles: string[];
  primary_role: string | null;
  primary_affiliation: string | null;
  affiliation_role: string | null;
  influence_score: number | null;
  influence_components?: Record<string, number | string> | null;
  influence_explanation?: string | null;
  influence_methodology_version?: string | null;
  influence_source_confidence?: number | null;
  influence_source_refs?: SourceRef[];
  confidence_score: number;
  source_refs: SourceRef[];
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
};

export type OpportunityHeatmapCell = {
  id: string;
  category: string;
  geo_code: string;
  geo_name: string;
  geo_level: string;
  lat: number | null;
  lng: number | null;
  supply_count: number;
  operator_ids: string[];
  population: number | null;
  business_count: number | null;
  opportunity_score: number;
  component_breakdown: Record<string, unknown>;
  calculation_method: string;
  source_refs: SourceRef[];
  confidence_score: number;
  trace_payload: Record<string, unknown>;
  generated_at: string;
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
};

export type OpportunityScorecard = {
  id: string;
  category: string;
  geo_code: string;
  geo_name: string;
  geo_level: string;
  opportunity_score: number;
  component_breakdown: Record<string, unknown>;
  source_refs: SourceRef[];
  confidence_score: number;
  calculation_method: string;
  caveat: string;
  generated_at: string;
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
};

export type OpportunityProposition = {
  id: string;
  heatmap_cell_id: string;
  headline: string;
  summary: string;
  category: string;
  geo_code: string;
  geo_name: string;
  geo_level: string;
  area: string;
  municipality: string | null;
  competitor_count_within_radius: number;
  competitor_radius_km: number;
  population: number | null;
  business_count: number | null;
  demand_source: string;
  supporting_signals: Array<{
    kind: string;
    label: string;
    raw_value: number | string | null;
    radius_km?: number;
    source_refs: SourceRef[];
  }>;
  component_breakdown: Record<string, unknown>;
  opportunity_score: number;
  confidence: number;
  confidence_score: number;
  source_refs: SourceRef[];
  generated_at: string;
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
};

export type CategoryVelocity = {
  id: string;
  category: string;
  window_days: number;
  new_operator_count: number;
  job_velocity_count: number;
  event_velocity_count: number;
  news_velocity_count: number;
  component_breakdown: Record<string, unknown>;
  source_refs: SourceRef[];
  confidence_score: number;
  calculated_at: string;
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
};

export type BriefSectionKey =
  | "changed_operators"
  | "new_signals"
  | "opportunity_movement"
  | "new_reachable_leads";

export type BriefSectionItem = {
  id: string;
  item_type: string;
  title: string;
  summary: string;
  source_refs: SourceRef[];
  confidence_score: number;
  operator_id?: string;
  signal_id?: string;
  scorecard_id?: string;
  name?: string;
  categories?: string[];
  primary_category?: string;
  status?: string;
  municipality?: string | null;
  neighborhood?: string | null;
  signal_type?: string;
  severity?: string;
  trust_tier?: string;
  geo_name?: string;
  category?: string;
  opportunity_score?: number;
  previous_score?: number | null;
  delta?: number | null;
  movement?: string;
  contact_types?: string[];
  contact_count?: number;
};

export type BriefAction = {
  id: string;
  title: string;
  summary: string;
  action_type: string;
  evidence_rows: Array<{
    section: BriefSectionKey;
    item_id: string;
    title: string;
    source_refs: SourceRef[];
  }>;
  source_refs: SourceRef[];
};

export type DailyBrief = {
  id: string;
  brief_date: string;
  generated_at: string;
  window_start: string;
  window_end: string;
  status: "material_changes" | "no_material_changes" | "initial_snapshot";
  brief_text: string;
  sections: Record<BriefSectionKey, BriefSectionItem[]>;
  top_actions: BriefAction[];
  counts: Record<string, number | boolean>;
  source_refs: SourceRef[];
  narrative_model: string;
  freshness_at?: string | null;
  freshness_age_hours?: number | null;
};

export type ObservabilitySummary = {
  runtime: {
    api_requests_total: number;
    api_errors_total: number;
    api_latency_ms_avg: number;
    map_query_latency_ms_avg: number;
  };
  database?: {
    wellness_contact_coverage?: {
      operator_count: number;
      with_contact_count: number;
      with_phone_count: number;
      with_email_count: number;
      with_website_count: number;
      coverage_ratio: number;
    };
  };
  alerts: Array<{
    condition: string;
    firing: boolean;
    severity: string;
    summary: string;
  }>;
};

export type TrendTile = {
  term: string;
  city: string;
  geography_code: string | null;
  growth_class: string;
  series: Array<{ period: string; value: number }>;
  source_name: string;
  fetched_at: string;
  source_refs: SourceRef[];
  confidence_score: number;
  is_stub: boolean;
  methodology: string;
};

export type GraphNode = {
  id: string;
  node_type: "person" | "organization" | "operator" | "event";
  entity_id: string;
  label: string;
  primary_category: string | null;
  centrality: number;
  community: number;
  x: number | null;
  y: number | null;
  source_refs: SourceRef[];
  confidence_score: number;
  payload: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  weight: number;
  source_refs: SourceRef[];
  confidence_score: number;
  payload: Record<string, unknown>;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_AUTH_TOKEN = import.meta.env.VITE_API_AUTH_TOKEN as string | undefined;

async function getJson<T>(
  path: string,
  options: { auth?: boolean; optional?: boolean } = {}
): Promise<T | null> {
  if (options.auth && !API_AUTH_TOKEN && options.optional) {
    return null;
  }
  const headers = new Headers();
  if (options.auth && API_AUTH_TOKEN) {
    headers.set("Authorization", `Bearer ${API_AUTH_TOKEN}`);
  }
  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (options.optional && (response.status === 401 || response.status === 403)) {
    return null;
  }
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
  if (!data) {
    return [];
  }
  return data.items;
}

export async function fetchSignals(operatorId?: string): Promise<Signal[]> {
  const params = new URLSearchParams({ bbox: "-123.3,49.0,-122.5,49.4" });
  if (operatorId) {
    params.set("related_operator_id", operatorId);
  }
  const data = await getJson<{ items: Signal[] }>(`/signals?${params.toString()}`);
  if (!data) {
    return [];
  }
  return data.items;
}

export async function fetchSourceRuns(): Promise<SourceRun[]> {
  const data = await getJson<{ items: SourceRun[] }>("/admin/source-runs?limit=5", {
    auth: true,
    optional: true
  });
  return data?.items ?? [];
}

export async function fetchSourceFreshness(): Promise<SourceFreshness[]> {
  const data = await getJson<{ items: SourceFreshness[] }>("/admin/source-freshness", {
    auth: true,
    optional: true
  });
  return data?.items ?? [];
}

export async function fetchObservability(): Promise<ObservabilitySummary | null> {
  return getJson<ObservabilitySummary>("/admin/observability", { auth: true, optional: true });
}

export async function fetchPeople(sort = "confidence"): Promise<Person[]> {
  const params = new URLSearchParams({ sort });
  const data = await getJson<{ items: Person[] }>(`/people?${params.toString()}`);
  if (!data) {
    return [];
  }
  return data.items;
}

export async function fetchWhitespace(
  category: string,
  geoLevel = "CSD"
): Promise<OpportunityHeatmapCell[]> {
  const params = new URLSearchParams({ category, geo_level: geoLevel });
  const data = await getJson<{ items: OpportunityHeatmapCell[] }>(
    `/analytics/whitespace?${params.toString()}`
  );
  if (!data) {
    return [];
  }
  return data.items;
}

export async function fetchOpportunityScorecards(
  category: string,
  geoLevel = "CSD"
): Promise<OpportunityScorecard[]> {
  const params = new URLSearchParams({ category, geo_level: geoLevel });
  const data = await getJson<{ items: OpportunityScorecard[] }>(
    `/analytics/opportunity-scorecards?${params.toString()}`
  );
  if (!data) {
    return [];
  }
  return data.items;
}

export async function fetchPropositions(
  category: string,
  geoLevel = "neighborhood"
): Promise<OpportunityProposition[]> {
  const params = new URLSearchParams({ category, geo_level: geoLevel });
  const data = await getJson<{ items: OpportunityProposition[] }>(
    `/api/propositions?${params.toString()}`
  );
  return data?.items ?? [];
}

export async function fetchCategoryVelocity(category: string): Promise<CategoryVelocity[]> {
  const params = new URLSearchParams({ category });
  const data = await getJson<{ items: CategoryVelocity[] }>(
    `/analytics/category-velocity?${params.toString()}`
  );
  if (!data) {
    return [];
  }
  return data.items;
}

export async function fetchDailyBrief(): Promise<DailyBrief | null> {
  try {
    return await getJson<DailyBrief>("/api/brief");
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("404 ")) {
      return null;
    }
    throw err;
  }
}

export async function fetchTrends(): Promise<TrendTile[]> {
  const data = await getJson<{ items: TrendTile[] }>("/trends");
  return data?.items ?? [];
}

export async function fetchPeopleGraph(): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  return (
    (await getJson<{ nodes: GraphNode[]; edges: GraphEdge[] }>("/people-graph")) ?? {
      nodes: [],
      edges: []
    }
  );
}
