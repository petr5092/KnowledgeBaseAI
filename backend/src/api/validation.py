from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict
from src.services.validation import validate_canonical_graph_snapshot
from src.api.common import ApiError

router = APIRouter(prefix="/v1/validation", tags=["Валидация"])

class GraphSnapshotInput(BaseModel):
    snapshot: Dict

class ValidationResult(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]

@router.post("/graph_snapshot", summary="Валидация снимка графа", description="Проверяет канонический снимок графа на согласованность и правила целостности.", response_model=ValidationResult, responses={422: {"model": ApiError, "description": "Неверная структура снапшота"}})
async def graph_snapshot(payload: GraphSnapshotInput) -> Dict:
    """
    Принимает:
      - snapshot: объект с полями nodes и edges

    Возвращает:
      - ok: флаг корректности
      - errors: список ошибок
      - warnings: список предупреждений
    """
    return validate_canonical_graph_snapshot(payload.snapshot)
