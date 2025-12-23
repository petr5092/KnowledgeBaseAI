export type ApiError = {
  status: number
  message: string
  details?: unknown
}

export class HttpError extends Error {
  status: number
  details?: unknown

  constructor(status: number, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.details = details
  }
}

function getApiBaseUrl() {
  const w = window as unknown as { __ENV__?: Record<string, string> }
  const fromEnvJs = w.__ENV__?.VITE_API_BASE_URL
  return fromEnvJs || ''
}

async function parseBody(res: Response) {
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return (await res.json()) as unknown
  return await res.text()
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBaseUrl()
  const url = `${base}${path}`

  const res = await fetch(url, init)
  if (!res.ok) {
    const body = await parseBody(res)
    const message = typeof body === 'string' ? body : JSON.stringify(body)
    throw new HttpError(res.status, message || `HTTP ${res.status}`, body)
  }

  return (await parseBody(res)) as T
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
  return apiFetch<ViewportResponse>(`/v1/graph/viewport?${qs.toString()}`)
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
  subject_uid: string | null
  progress: Record<string, number>
  limit: number
}

export async function postRoadmap(body: RoadmapRequest) {
  return apiFetch<{ items: unknown[] }>(`/v1/graph/roadmap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function postChat(body: { question: string; from_uid: string; to_uid: string }) {
  return apiFetch<unknown>(`/v1/graph/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export type AnalyticsStats = {
  graph: { total_nodes: number; avg_out_degree: number; density: number }
  ai: { tokens_input: number; tokens_output: number; cost_usd: number; latency_ms: number }
  quality: { orphans: number; auto_merged: number }
}

export async function getAnalyticsStats() {
  return apiFetch<AnalyticsStats>(`/v1/analytics/stats`)
}

export type AssistantAction = 'explain_relation' | 'viewport' | 'roadmap' | 'analytics' | 'questions'

export async function assistantChat(body: {
  action?: AssistantAction
  message: string
  from_uid?: string
  to_uid?: string
  center_uid?: string
  depth?: number
  subject_uid?: string
  progress?: Record<string, number>
  limit?: number
  count?: number
  difficulty_min?: number
  difficulty_max?: number
  exclude?: string[]
}) {
  return apiFetch<unknown>(`/v1/assistant/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function getAssistantTools() {
  return apiFetch<{ tools: Array<{ name: string; description: string }> }>(`/v1/assistant/tools`)
}
