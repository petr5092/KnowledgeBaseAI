import React, { useState } from "react"
import { ReviewDiff } from "./ReviewDiff"
import { ImpactGraph } from "./ImpactGraph"

export function ReviewAndImpact({ proposalId }: { proposalId: string }) {
  const [selectedUids, setSelectedUids] = useState<string[]>([])
  const [types, setTypes] = useState<string[]>([])
  return React.createElement(
    "div",
    { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 } },
    React.createElement("div", null,
      React.createElement("h3", null, "Diff"),
      React.createElement(ReviewDiff, { proposalId, onSelect: setSelectedUids })
    ),
    React.createElement("div", null,
      React.createElement("h3", null, "Impact"),
      React.createElement("div", null,
        React.createElement("label", null, "Filter types: "),
        React.createElement("input", {
          value: types.join(","),
          onChange: e => setTypes(e.currentTarget.value.split(",").map(x => x.trim()).filter(Boolean))
        })
      ),
      React.createElement(ImpactGraph, { proposalId, depth: 1, types })
    )
  )
}
