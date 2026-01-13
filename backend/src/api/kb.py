from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Optional
import asyncio
from src.services.kb.builder import generate_subject_with_llm
from src.services.kb.jsonl_io import get_subject_dir
from src.services.graph.utils import sync_from_jsonl_dir

router = APIRouter(prefix="/kb", tags=["kb"])

class GenerateRequest(BaseModel):
    subject: str
    language: str
    import_into_graph: Optional[bool] = False
    limits: Optional[Dict] = None

@router.post("/generate_smart")
async def generate_smart(req: GenerateRequest) -> Dict:
    res = await generate_subject_with_llm(req.subject, req.language, req.limits or {})
    base_dir = res.get("base_dir")
    out = {"ok": res.get("ok"), "base_dir": base_dir}
    if req.import_into_graph and base_dir:
        imp = sync_from_jsonl_dir(base_dir)
        out["import"] = imp
    return out
