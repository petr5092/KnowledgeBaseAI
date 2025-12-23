from fastapi import APIRouter, Depends, Header, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Dict, List
from src.services.curriculum.repo import create_curriculum, add_curriculum_nodes, get_graph_view
from src.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка: учебные планы"])

class CreateCurriculumInput(BaseModel):
    code: str
    title: str
    standard: str
    language: str

@router.post("/curriculum", summary="Создать учебный план", description="Создает новый учебный план в Postgres и возвращает его идентификатор.")
async def admin_create_curriculum(payload: CreateCurriculumInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - code: код плана
      - title: название
      - standard: образовательный стандарт
      - language: язык

    Возвращает:
      - ok: True/False
      - id: идентификатор созданного плана (при успехе)
      - error: текст ошибки (если Postgres не настроен)
    """
    return create_curriculum(payload.code, payload.title, payload.standard, payload.language)

class CurriculumNodeInput(BaseModel):
    code: str
    nodes: List[Dict]

@router.post("/curriculum/nodes", summary="Добавить узлы плана", description="Добавляет узлы (канонические UID) в учебный план с порядком и обязательностью.")
async def admin_add_curriculum_nodes(payload: CurriculumNodeInput, x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - code: код плана
      - nodes: список объектов {kind, canonical_uid, order_index, is_required}

    Возвращает:
      - ok: True/False
      - error: текст ошибки (если план не найден или Postgres не настроен)
    """
    return add_curriculum_nodes(payload.code, payload.nodes)

@router.get("/curriculum/graph_view", summary="Просмотр плана", description="Возвращает состав учебного плана в виде списка узлов.")
async def admin_curriculum_graph_view(code: str) -> Dict:
    """
    Принимает:
      - code: код плана

    Возвращает:
      - ok: True/False
      - nodes: список узлов {kind, canonical_uid, order_index} при успехе
      - error: текст ошибки
    """
    return get_graph_view(code)
