from fastapi import APIRouter, Depends
from typing import Dict
from src.services.graph.neo4j_repo import purge_user_artifacts
from src.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])

@router.post("/purge_users")
async def purge_users() -> Dict:
    return purge_user_artifacts()
