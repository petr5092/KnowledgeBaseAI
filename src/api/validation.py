from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict
from src.services.validation import validate_canonical_graph_snapshot

router = APIRouter(prefix="/v1/validation")

class GraphSnapshotInput(BaseModel):
    snapshot: Dict

@router.post("/graph_snapshot")
async def graph_snapshot(payload: GraphSnapshotInput) -> Dict:
    return validate_canonical_graph_snapshot(payload.snapshot)

