from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, List
from src.services.curriculum.repo import create_curriculum, add_curriculum_nodes, get_graph_view
from src.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])

class CreateCurriculumInput(BaseModel):
    code: str
    title: str
    standard: str
    language: str

@router.post("/curriculum")
async def admin_create_curriculum(payload: CreateCurriculumInput) -> Dict:
    return create_curriculum(payload.code, payload.title, payload.standard, payload.language)

class CurriculumNodeInput(BaseModel):
    code: str
    nodes: List[Dict]

@router.post("/curriculum/nodes")
async def admin_add_curriculum_nodes(payload: CurriculumNodeInput) -> Dict:
    return add_curriculum_nodes(payload.code, payload.nodes)

@router.get("/curriculum/graph_view")
async def admin_curriculum_graph_view(code: str) -> Dict:
    return get_graph_view(code)
