from fastapi import APIRouter
from typing import Dict
from kb_jobs import start_rebuild_async, get_job_status
from neo4j_utils import recompute_relationship_weights

router = APIRouter(prefix="/v1/maintenance")

@router.post("/kb/rebuild_async")
async def kb_rebuild_async() -> Dict:
    return start_rebuild_async()

@router.get("/kb/rebuild_status")
async def kb_rebuild_status(job_id: str) -> Dict:
    return get_job_status(job_id)

@router.post("/recompute_links")
async def recompute_links() -> Dict:
    stats = recompute_relationship_weights()
    return {"ok": True, "stats": stats}
