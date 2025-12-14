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

export type ViewportResponse = {
  nodes: Array<{ uid: string; title?: string; kind?: string }>
  edges: Array<{ source: string; target: string; kind?: string; weight?: number }>
  center_uid: string
  depth: number
}

export async function getViewport(params: { center_uid: string; depth: number }) {
  const qs = new URLSearchParams({ center_uid: params.center_uid, depth: String(params.depth) })
  return apiFetch<ViewportResponse>(`/v1/graph/viewport?${qs.toString()}`)
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
