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
  const fromVite = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL;
  return fromEnvJs || fromVite || "";
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

// 4.2 Graph Data Model
export type NodeKind = 'Subject' | 'Section' | 'Topic' | 'Skill' | 'Resource' | 'concept' | 'skill' | 'resource' // Union of real & required types

export interface GraphNode {
  uid: string
  title?: string
  kind: NodeKind
  data?: Record<string, unknown>
  [key: string]: unknown // Allow extra props from Neo4j
}

export interface GraphEdge {
  source: string
  target: string
  relation: string // In Neo4j response this might be 'type' or 'kind'
  weight?: number
  [key: string]: unknown
}

export type ViewportResponse = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  center_uid: string
  depth: number
}

export async function getViewport(params: { center_uid: string; depth: number }) {
  const qs = new URLSearchParams({ center_uid: params.center_uid, depth: String(params.depth) })
  const raw = await apiFetch<unknown>(`/v1/graph/viewport?${qs.toString()}`)
  const obj = raw as Record<string, unknown>
  const nodesRaw = (obj["nodes"] as any[]) ?? []
  const edgesRaw = (obj["edges"] as any[]) ?? []
  const nodes: GraphNode[] = nodesRaw.map((n) => {
    const uid = n?.uid ?? String(n?.id ?? "")
    const title = n?.title ?? n?.label ?? undefined
    const kind = (n?.kind ?? n?.labels?.[0] ?? "concept") as NodeKind
    const data = { id: n?.id ?? uid, labels: n?.labels ?? [], ...((n?.data as Record<string, unknown>) ?? {}) }
    return { uid, title, kind, data }
  })
  const edges: GraphEdge[] = edgesRaw.map((e) => {
    const source = e?.source ?? e?.from ?? ""
    const target = e?.target ?? e?.to ?? ""
    const relation = e?.relation ?? e?.type ?? e?.kind ?? undefined
    const rest = e as Record<string, unknown>
    return { source: String(source), target: String(target), relation: relation ? String(relation) : undefined, ...rest }
  })
  return { nodes, edges, center_uid: params.center_uid, depth: params.depth } satisfies ViewportResponse
}

export type NodeDetails = {
  uid: string
  title?: string
  kind?: string
  labels?: string[]
  incoming: Array<{ rel: string; uid: string; title?: string }>
  outgoing: Array<{ rel: string; uid: string; title?: string }>
  [key: string]: unknown
}

export async function getNodeDetails(uid: string) {
  return apiFetch<NodeDetails>(`/v1/graph/node/${uid}`)
}

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
