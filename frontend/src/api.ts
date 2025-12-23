import {
  ViewportResponseSchema,
  RoadmapResponseSchema,
  ChatResponseSchema,
  AnalyticsStatsSchema,
  AssistantActionSchema,
  AssistantToolsSchema,
} from "./schemas";

import type {
  ViewportResponse,
  RoadmapResponse,
  ChatResponse,
  AnalyticsStats,
  AssistantAction,
  AssistantTools,
} from "./schemas";

export type ApiError = {
  status: number;
  message: string;
  details?: unknown;
};

export class HttpError extends Error {
  status: number;
  details?: unknown;

  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

function getApiBaseUrl() {
  const w = window as unknown as { __ENV__?: Record<string, string> };
  const fromEnvJs = w.__ENV__?.VITE_API_BASE_URL;
  return fromEnvJs || "";
}

async function parseBody(res: Response) {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as unknown;
  return await res.text();
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBaseUrl();
  const url = `${base}${path}`;

  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await parseBody(res);
    const message = typeof body === "string" ? body : JSON.stringify(body);
    throw new HttpError(res.status, message || `HTTP ${res.status}`, body);
  }

  return (await parseBody(res)) as T;
}

// --- Viewport ---
export async function getViewport(params: { center_uid: string; depth: number }): Promise<ViewportResponse> {
  const qs = new URLSearchParams({ center_uid: params.center_uid, depth: String(params.depth) });
  const raw = await apiFetch<unknown>(`/v1/graph/viewport?${qs.toString()}`);
  return ViewportResponseSchema.parse(raw);
}

// --- Roadmap ---
export type RoadmapRequest = {
  subject_uid: string | null;
  progress: Record<string, number>;
  limit: number;
};

export async function postRoadmap(body: RoadmapRequest): Promise<RoadmapResponse> {
  const raw = await apiFetch<unknown>(`/v1/graph/roadmap`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return RoadmapResponseSchema.parse(raw);
}

// --- Chat ---
export async function postChat(body: { question: string; from_uid: string; to_uid: string }): Promise<ChatResponse> {
  const raw = await apiFetch<unknown>(`/v1/graph/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return ChatResponseSchema.parse(raw);
}

// --- Analytics ---
export async function getAnalyticsStats(): Promise<AnalyticsStats> {
  const raw = await apiFetch<unknown>(`/v1/analytics/stats`);
  return AnalyticsStatsSchema.parse(raw);
}

// --- Assistant Chat ---
export async function assistantChat(body: {
  action?: AssistantAction;
  message: string;
  from_uid?: string;
  to_uid?: string;
  center_uid?: string;
  depth?: number;
  subject_uid?: string;
  progress?: Record<string, number>;
  limit?: number;
  count?: number;
  difficulty_min?: number;
  difficulty_max?: number;
  exclude?: string[];
}) {
  const raw = await apiFetch<unknown>(`/v1/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  // Если сервер возвращает action, можно валидировать:
  // return AssistantActionSchema.parse(raw);
  return raw;
}

// --- Assistant Tools ---
export async function getAssistantTools(): Promise<AssistantTools> {
  const raw = await apiFetch<unknown>(`/v1/assistant/tools`);
  return AssistantToolsSchema.parse(raw);
}
