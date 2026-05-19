export type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  name: string;
  status: JobStatus;
  seed_urls: string[];
  extraction_schema: Record<string, unknown>;
  crawl_config: Record<string, unknown>;
  priority: number;
  max_pages: number;
  pages_discovered: number;
  pages_processed: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface PageSummary {
  id: string;
  job_id: string;
  url: string;
  canonical_url: string | null;
  domain: string;
  status: string;
  http_status: number | null;
  content_type: string | null;
  title: string | null;
  raw_html_sha256: string | null;
  error_message: string | null;
  fetched_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobDetail extends Job {
  pages: PageSummary[];
}

export interface JobList {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface ExtractedRecord {
  id: string;
  page_id: string;
  job_id: string;
  url: string;
  extractor_name: string;
  schema_name: string;
  data: Record<string, unknown>;
  confidence: string;
  validation_errors: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

export interface ExtractedDataList {
  items: ExtractedRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface AiSchemaResponse {
  extraction_schema: Record<string, unknown>;
  pydantic_model_code: string;
  provider: string;
  raw: Record<string, unknown>;
}

export interface SystemHealth {
  status: "ok" | "degraded";
  dependencies: Record<string, { status: string; detail: string | null }>;
  workers: Record<string, string>;
}

export interface CapabilityCheck {
  name: string;
  status: "ok" | "degraded" | "down";
  detail: string;
  remediation: string | null;
}

export interface SystemReadiness {
  status: "ok" | "degraded" | "down";
  checks: CapabilityCheck[];
  working: string[];
  degraded: string[];
  broken: string[];
}

export type AlertSeverity = "info" | "warning" | "critical";
export type AlertStatus = "open" | "acknowledged" | "resolved";

export interface AlertRecord {
  id: string;
  severity: AlertSeverity;
  title: string;
  status: AlertStatus;
  context: Record<string, unknown>;
  detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertList {
  items: AlertRecord[];
  total: number;
  limit: number;
  offset: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("webintel_access_token") : null;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers
    },
    ...init
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  }
  return response.json() as Promise<T>;
}

export const api = {
  createJob: (payload: Record<string, unknown>) =>
    request<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listJobs: () => request<JobList>("/jobs?limit=50"),
  getJob: (jobId: string) => request<JobDetail>(`/jobs/${jobId}`),
  cancelJob: (jobId: string) => request<{ id: string; status: JobStatus; message: string }>(`/jobs/${jobId}/cancel`, { method: "POST" }),
  listData: () => request<ExtractedDataList>("/data?limit=30"),
  health: () => request<SystemHealth>("/system/health"),
  readiness: () => request<SystemReadiness>("/system/readiness"),
  generateSchema: (instruction: string) =>
    request<AiSchemaResponse>("/ai-engine/schemas", {
      method: "POST",
      body: JSON.stringify({ instruction })
    }),
  listAlerts: () => request<AlertList>("/alerts?limit=50"),
  ackAlert: (alertId: string) => request<{ id: string; status: AlertStatus; message: string }>(`/alerts/${alertId}/ack`, { method: "POST" })
};
