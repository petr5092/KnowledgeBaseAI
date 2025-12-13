from fastapi import APIRouter
from typing import Dict
from src.services.graph.neo4j_repo import purge_user_artifacts

router = APIRouter(prefix="/v1/admin")

@router.post("/purge_users")
async def purge_users() -> Dict:
    return purge_user_artifacts()
