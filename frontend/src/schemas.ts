import { optional, z } from "zod";

// --- Узлы графа ---
export const GraphNodeSchema = z.object({
  uid: z.string(),
  title: z.string().optional(),
  kind: z.enum(["concept", "skill", "resource"]).optional(),
  color: z.string().optional(),
  shape: z.string().optional(),
  data: z.record(z.string(), z.unknown()).optional().transform((val) => val ?? {}),
});

// --- Рёбра графа ---
export const GraphEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  relation: z.string().optional(),
  kind: z.string().optional(),
  weight: z.number().optional(),
});

// --- Viewport ---
export const ViewportResponseSchema = z.object({
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
  center_uid: z.string(),
  depth: z.number(),
});

// --- Roadmap ---
export const RoadmapResponseSchema = z.object({
  items: z.array(z.unknown()), // уточни позже структуру
});

// --- Chat ---
export const ChatResponseSchema = z.unknown(); // пока неизвестная структура

// --- Analytics ---
export const AnalyticsStatsSchema = z.object({
  graph: z.object({
    total_nodes: z.number(),
    avg_out_degree: z.number(),
    density: z.number(),
  }),
  ai: z.object({
    tokens_input: z.number(),
    tokens_output: z.number(),
    cost_usd: z.number(),
    latency_ms: z.number(),
  }),
  quality: z.object({
    orphans: z.number(),
    auto_merged: z.number(),
  }),
});

// --- Assistant Actions (discriminated union) ---
export const AssistantActionSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("navigateToNode"),
    payload: z.object({ uid: z.string() }),
  }),
  z.object({
    type: z.literal("showRelated"),
    payload: z.object({ related: z.array(z.string()) }),
  }),
  z.object({
    type: z.literal("openResource"),
    payload: z.object({ url: z.string().url() }),
  }),
]);

// --- Assistant Tools ---
export const AssistantToolsSchema = z.object({
  tools: z.array(
    z.object({
      name: z.string(),
      description: z.string(),
    })
  ),
});

// Типы
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type ViewportResponse = z.infer<typeof ViewportResponseSchema>;
export type RoadmapResponse = z.infer<typeof RoadmapResponseSchema>;
export type ChatResponse = z.infer<typeof ChatResponseSchema>;
export type AnalyticsStats = z.infer<typeof AnalyticsStatsSchema>;
export type AssistantAction = z.infer<typeof AssistantActionSchema>;
export type AssistantTools = z.infer<typeof AssistantToolsSchema>;
