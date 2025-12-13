from fastapi import APIRouter
from typing import Dict
from src.services.graph.neo4j_repo import read_graph
import math

router = APIRouter(prefix="/v1/analytics")

@router.get("/stats")
async def stats() -> Dict:
    nodes, edges = read_graph()
    n = len(nodes)
    m = len(edges)
    out_degree: Dict[int, int] = {}
    for e in edges:
        out_degree[e["from"]] = out_degree.get(e["from"], 0) + 1
    avg_out = (sum(out_degree.values()) / n) if n else 0.0
    density = (m / (n * (n - 1))) if n > 1 else 0.0
    density = float(f"{density:.6f}")
    return {
        "graph": {"total_nodes": n, "avg_out_degree": avg_out, "density": density},
        "ai": {"tokens_input": 0, "tokens_output": 0, "cost_usd": 0.0, "latency_ms": 0},
        "quality": {"orphans": 0, "auto_merged": 0},
    }
