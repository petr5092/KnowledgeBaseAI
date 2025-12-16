import React, { useEffect, useState } from "react"

type NodeItem = { uid?: string; name?: string; type?: string }
type EdgeItem = { from?: number; to?: number; type?: string }

async function fetchImpact(proposalId: string, depth: number): Promise<{ nodes: NodeItem[]; edges: EdgeItem[] }> {
  const res = await fetch(`/v1/proposals/${proposalId}/impact?depth=${depth}`)
  if (!res.ok) throw new Error("failed to fetch impact")
  return res.json()
}

export function ImpactGraph({ proposalId, depth = 1 }: { proposalId: string; depth?: number }) {
  const [nodes, setNodes] = useState<NodeItem[]>([])
  const [edges, setEdges] = useState<EdgeItem[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetchImpact(proposalId, depth)
      .then(d => {
        setNodes(d.nodes || [])
        setEdges(d.edges || [])
      })
      .catch(e => setError(String(e)))
  }, [proposalId, depth])
  if (error) return React.createElement("div", null, `Error: ${error}`)
  return React.createElement(
    "div",
    null,
    React.createElement("h3", null, "Impact Subgraph"),
    React.createElement(
      "div",
      { style: { display: "flex", gap: 16 } },
      React.createElement(
        "div",
        { style: { flex: 1 } },
        React.createElement("h4", null, "Nodes"),
        React.createElement("ul", null, nodes.map((n, i) => React.createElement("li", { key: i }, `${n.uid} ${n.name ? "(" + n.name + ")" : ""} ${n.type ? "[" + n.type + "]" : ""}`)))
      ),
      React.createElement(
        "div",
        { style: { flex: 1 } },
        React.createElement("h4", null, "Edges"),
        React.createElement("ul", null, edges.map((e, i) => React.createElement("li", { key: i }, `${e.type} ${e.from} -> ${e.to}`)))
      )
    )
  )
}
