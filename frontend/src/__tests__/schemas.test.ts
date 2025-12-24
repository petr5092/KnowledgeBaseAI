import { describe, it, expect } from "vitest";
import {
  GraphNodeSchema,
  GraphEdgeSchema,
  ViewportResponseSchema,
  AssistantActionSchema,
  AnalyticsStatsSchema,
  RoadmapResponseSchema,
  AssistantToolsSchema,
} from "../schemas";
import type { AssistantAction } from "../schemas";


describe("GraphNodeSchema", () => {
  it("валидирует корректный узел", () => {
    const node = { uid: "n1", kind: "concept", color: "red", shape: "circle" };
    const parsed = GraphNodeSchema.parse(node);
    expect(parsed.uid).toBe("n1");
  });

  it("бросает ошибку при отсутствии uid", () => {
    const badNode = { kind: "concept" };
    expect(() => GraphNodeSchema.parse(badNode)).toThrow();
  });
});

describe("GraphEdgeSchema", () => {
  it("валидирует корректное ребро", () => {
    const edge = { source: "n1", target: "n2", relation: "depends" };
    const parsed = GraphEdgeSchema.parse(edge);
    expect(parsed.source).toBe("n1");
  });

  it("бросает ошибку при отсутствии source", () => {
    const badEdge = { target: "n2" };
    expect(() => GraphEdgeSchema.parse(badEdge)).toThrow();
  });
});

describe("ViewportResponseSchema", () => {
  it("валидирует корректный ответ", () => {
    const data = {
      nodes: [{ uid: "n1", kind: "concept" }],
      edges: [{ source: "n1", target: "n2", relation: "depends" }],
      center_uid: "n1",
      depth: 2,
    };
    const parsed = ViewportResponseSchema.parse(data);
    expect(parsed.center_uid).toBe("n1");
  });

  it("бросает ошибку при отсутствии center_uid", () => {
    const badData = { nodes: [], edges: [], depth: 1 };
    expect(() => ViewportResponseSchema.parse(badData)).toThrow();
  });
});

describe("AssistantActionSchema", () => {
  it("валидирует navigateToNode", () => {
    const action: AssistantAction = { type: "navigateToNode", payload: { uid: "n1" } };
    const parsed = AssistantActionSchema.parse(action);

    // TS теперь знает, что если type === "navigateToNode", то payload имеет uid
    if (parsed.type === "navigateToNode") {
      expect(parsed.payload.uid).toBe("n1");
    }
  });

  it("бросает ошибку при неправильном payload", () => {
    const badAction = { type: "navigateToNode", payload: { wrong: "field" } };
    expect(() => AssistantActionSchema.parse(badAction)).toThrow();
  });
});


describe("AnalyticsStatsSchema", () => {
  it("валидирует корректные метрики", () => {
    const stats = {
      graph: { total_nodes: 10, avg_out_degree: 2, density: 0.5 },
      ai: { tokens_input: 100, tokens_output: 200, cost_usd: 0.01, latency_ms: 50 },
      quality: { orphans: 1, auto_merged: 0 },
    };
    const parsed = AnalyticsStatsSchema.parse(stats);
    expect(parsed.graph.total_nodes).toBe(10);
  });

  it("бросает ошибку при отсутствии поля graph", () => {
    const badStats = { ai: {}, quality: {} };
    expect(() => AnalyticsStatsSchema.parse(badStats)).toThrow();
  });
});

describe("RoadmapResponseSchema", () => {
  it("валидирует список items", () => {
    const data = { items: [{ foo: "bar" }] };
    const parsed = RoadmapResponseSchema.parse(data);
    expect(parsed.items.length).toBe(1);
  });

  it("бросает ошибку при отсутствии items", () => {
    const badData = {};
    expect(() => RoadmapResponseSchema.parse(badData)).toThrow();
  });
});

describe("AssistantToolsSchema", () => {
  it("валидирует список инструментов", () => {
    const data = { tools: [{ name: "tool1", description: "desc1" }] };
    const parsed = AssistantToolsSchema.parse(data);
    expect(parsed.tools[0].name).toBe("tool1");
  });

  it("бросает ошибку при отсутствии name", () => {
    const badData = { tools: [{ description: "desc1" }] };
    expect(() => AssistantToolsSchema.parse(badData)).toThrow();
  });
});
