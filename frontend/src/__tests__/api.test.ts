import { describe, it, expect, vi } from "vitest";
import {
  getViewport,
  postRoadmap,
  postChat,
  getAnalyticsStats,
  assistantChat,
  getAssistantTools,
} from "../api";

// --- Мокаем fetch ---
function mockFetchOk(data: any) {
  (globalThis.fetch as any) = vi.fn().mockResolvedValue({
    ok: true,
    headers: { get: () => "application/json" },
    json: async () => data,
  });
}

function mockFetchError(status = 500, body: any = { error: "server error" }) {
  (globalThis.fetch as any) = vi.fn().mockResolvedValue({
    ok: false,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
  });
}

describe("API layer", () => {
  it("getViewport возвращает валидные данные", async () => {
    mockFetchOk({
      nodes: [{ uid: "n1", kind: "concept" }],
      edges: [],
      center_uid: "n1",
      depth: 1,
    });

    const viewport = await getViewport({ center_uid: "n1", depth: 1 });
    expect(viewport.center_uid).toBe("n1");
    expect(viewport.nodes[0].uid).toBe("n1");
  });

  it("postRoadmap возвращает список items", async () => {
    mockFetchOk({ items: [{ foo: "bar" }] });

    const roadmap = await postRoadmap({
      subject_uid: "s1",
      progress: { n1: 0.5 },
      limit: 10,
    });
    expect(roadmap.items.length).toBe(1);
  });

  it("postChat возвращает unknown", async () => {
    mockFetchOk({ answer: "42" });

    const chat = await postChat({ question: "?", from_uid: "a", to_uid: "b" });
    expect(chat).toEqual({ answer: "42" });
  });

  it("getAnalyticsStats возвращает метрики", async () => {
    mockFetchOk({
      graph: { total_nodes: 10, avg_out_degree: 2, density: 0.5 },
      ai: { tokens_input: 100, tokens_output: 200, cost_usd: 0.01, latency_ms: 50 },
      quality: { orphans: 1, auto_merged: 0 },
    });

    const stats = await getAnalyticsStats();
    expect(stats.graph.total_nodes).toBe(10);
    expect(stats.ai.cost_usd).toBeCloseTo(0.01);
  });

  it("assistantChat возвращает unknown", async () => {
    mockFetchOk({ type: "navigateToNode", payload: { uid: "n1" } });

    const action = await assistantChat({ message: "test" });
    expect(action).toEqual({ type: "navigateToNode", payload: { uid: "n1" } });
  });

  it("getAssistantTools возвращает список инструментов", async () => {
    mockFetchOk({
      tools: [{ name: "tool1", description: "desc1" }],
    });

    const tools = await getAssistantTools();
    expect(tools.tools[0].name).toBe("tool1");
  });

  it("бросает HttpError при ошибке", async () => {
    mockFetchError();

    await expect(getViewport({ center_uid: "n1", depth: 1 })).rejects.toThrow();
  });
});
