import type {
  AlanInvestigation,
  CaseDetail,
  CaseSummary,
  ChatMessage,
  ChatResponse,
  Dashboard,
  Health,
  ReviewStatus,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  code: string;
  status: number;
  missing: string[];
  caseId: string | null;

  constructor(message: string, code: string, status: number, missing: string[] = [], caseId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.missing = missing;
    this.caseId = caseId;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(
      "The API is unreachable. Start the FastAPI server on port 8000 and try again.",
      "network_error",
      0,
    );
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    const record = (body ?? {}) as Record<string, unknown>;
    const error = (record.error ?? {}) as Record<string, unknown>;
    const detail = typeof record.detail === "string" ? record.detail : null;
    const message =
      (typeof error.message === "string" && error.message) ||
      detail ||
      `Request failed with HTTP ${response.status}.`;
    const code = typeof error.code === "string" ? error.code : "http_error";
    const missing = Array.isArray(error.missing) ? error.missing.map(String) : [];
    const caseId = typeof error.case_id === "string" ? error.case_id : null;
    throw new ApiError(message, code, response.status, missing, caseId);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  dashboard: () => request<Dashboard>("/api/dashboard"),
  cases: (limit = 200) => request<CaseSummary[]>(`/api/cases?limit=${limit}`),
  case: (id: string) => request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`),
  messages: (id: string) =>
    request<ChatMessage[]>(`/api/cases/${encodeURIComponent(id)}/messages`),

  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<CaseDetail>("/api/documents", { method: "POST", body: form });
  },

  review: (id: string, status: ReviewStatus, note: string, reviewer: string) =>
    request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note: note || null, reviewer: reviewer || null }),
    }),

  chat: (id: string, message: string) =>
    request<ChatResponse>(`/api/cases/${encodeURIComponent(id)}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }),

  startAlan: (id: string, question: string) =>
    request<AlanInvestigation>(`/api/cases/${encodeURIComponent(id)}/alan/investigations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),

  pollAlan: (executionId: string) =>
    request<AlanInvestigation>(
      `/api/alan/investigations/${encodeURIComponent(executionId)}`,
    ),

  alanRuns: (id: string) =>
    request<AlanInvestigation[]>(
      `/api/cases/${encodeURIComponent(id)}/alan/investigations`,
    ),
};