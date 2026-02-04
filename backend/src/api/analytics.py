from fastapi import APIRouter
from typing import Dict
from pydantic import BaseModel
from src.services.graph.neo4j_repo import read_graph
import math

router = APIRouter(prefix="/v1/analytics", tags=["Аналитика"])


class GraphStats(BaseModel):
    total_nodes: int
    avg_out_degree: float
    density: float


class AIStats(BaseModel):
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_ms: int


class QualityStats(BaseModel):
    orphans: int
    auto_merged: int


class StatsResponse(BaseModel):
    graph: GraphStats
    ai: AIStats
    quality: QualityStats


@router.get(
    "/stats",
    summary="Метрики графа",
    description="Возвращает сводные метрики графа знаний (число узлов, плотность, средняя исходящая степень).",
    response_model=StatsResponse,
    responses={
        500: {
            "description": "Внутренняя ошибка сервера",
            "content": {"application/json": {"example": {"code": "internal_error", "message": "graph store unavailable"}}},
        }
    },
)
async def stats(progress: Dict[str, float] | None = None) -> Dict:
    """
    Принимает:
      - progress (опционально): словарь {uid: mastery_score}

    Возвращает:
      - graph.total_nodes: количество узлов
      - graph.avg_out_degree: средняя исходящая степень
      - graph.density: плотность графа
      - user_completion_percent (если progress передан): % освоенных тем
      - topics_mastered (если progress передан): кол-во освоенных тем
      - topics_started (если progress передан): кол-во начатых тем
      - ai.*: заглушки метрик использования ИИ
      - quality.*: заглушки метрик качества контента
    """
    nodes, edges = read_graph()
    n = len(nodes)
    m = len(edges)
    out_degree: Dict[int, int] = {}
    for e in edges:
        out_degree[e["from"]] = out_degree.get(e["from"], 0) + 1
    avg_out = (sum(out_degree.values()) / n) if n else 0.0
    density = (m / (n * (n - 1))) if n > 1 else 0.0
    density = float(f"{density:.6f}")

    result = {
        "graph": {"total_nodes": n, "avg_out_degree": avg_out, "density": density},
        "ai": {"tokens_input": 0, "tokens_output": 0, "cost_usd": 0.0, "latency_ms": 0},
        "quality": {"orphans": 0, "auto_merged": 0},
    }

    # Add user-specific metrics if progress is provided
    if progress:
        topics_started = sum(1 for score in progress.values() if score > 0)
        topics_mastered = sum(1 for score in progress.values() if score >= 0.8)
        user_completion_percent = (
            topics_mastered / len(progress) * 100) if progress else 0.0

        result["user_completion_percent"] = round(user_completion_percent, 2)
        result["topics_mastered"] = topics_mastered
        result["topics_started"] = topics_started

    return result
