from fastapi import APIRouter
from typing import Dict

router = APIRouter(prefix="/v1/analytics")

@router.get("/stats")
async def stats() -> Dict:
    return {
        "graph": {"total_nodes": 0, "avg_out_degree": 0.0, "density": 0.0},
        "ai": {"tokens_input": 0, "tokens_output": 0, "cost_usd": 0.0, "latency_ms": 0},
        "quality": {"orphans": 0, "auto_merged": 0},
    }
