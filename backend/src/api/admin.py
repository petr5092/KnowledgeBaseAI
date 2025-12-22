from fastapi import APIRouter, Depends, Header, Security
from fastapi.security import HTTPBearer
from typing import Dict
from src.services.graph.neo4j_repo import purge_user_artifacts
from src.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка"])

@router.post("/purge_users", summary="Очистить пользователей", description="Удаляет узлы пользователей и их связи прогресса из графа.")
async def purge_users(x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> Dict:
    """
    Принимает:
      - нет входных параметров

    Возвращает:
      - deleted_users: количество удаленных узлов User
      - deleted_completed_rels: количество удаленных связей COMPLETED
    """
    return purge_user_artifacts()
