from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from src.services.reasoning.gaps import compute_gaps
from src.services.reasoning.next_best_topic import next_best_topics
from src.services.reasoning.roadmap import build_roadmap
from src.services.reasoning.mastery_update import update_mastery
from src.db.pg import outbox_add
from src.api.common import StandardResponse, ApiError

router = APIRouter(prefix="/v1/reasoning", tags=["Интеграция с LMS"])

class Progress(BaseModel):
    topics: Dict[str, float] = Field(default_factory=dict)
    skills: Dict[str, float] = Field(default_factory=dict)

class GapsRequest(BaseModel):
    subject_uid: str
    progress: Dict[str, float] = Field(default_factory=dict)
    goals: Optional[List[str]] = None
    prereq_threshold: float = 0.7

@router.post("/gaps", response_model=StandardResponse, responses={400: {"model": ApiError}})
async def gaps(req: GapsRequest):
    res = compute_gaps(req.subject_uid, req.progress, req.goals, req.prereq_threshold)
    return {"items": [], "meta": res}

class NextBestRequest(BaseModel):
    subject_uid: str
    progress: Dict[str, float] = Field(default_factory=dict)
    prereq_threshold: float = 0.7
    top_k: int = 5
    alpha: float = 0.5
    beta: float = 0.3

@router.post("/next-best-topic", response_model=StandardResponse, responses={400: {"model": ApiError}})
async def next_best_topic(req: NextBestRequest):
    res = next_best_topics(req.subject_uid, req.progress, req.prereq_threshold, req.top_k, req.alpha, req.beta)
    return {"items": res["items"], "meta": {}}

class RoadmapRequest(BaseModel):
    subject_uid: str
    progress: Dict[str, float] = Field(default_factory=dict)
    goals: Optional[List[str]] = None
    prereq_threshold: float = 0.7
    top_k: int = 10

@router.post("/roadmap", response_model=StandardResponse, responses={400: {"model": ApiError}})
async def roadmap(req: RoadmapRequest):
    res = build_roadmap(req.subject_uid, req.progress, req.goals, req.prereq_threshold, req.top_k)
    outbox_add(tenant_id="public", event_type="roadmap_generated", payload={"subject_uid": req.subject_uid, "count": len(res["items"])})
    return {"items": res["items"], "meta": res.get("meta", {})}

class MasteryUpdateRequest(BaseModel):
    entity_uid: str
    kind: str = Field(pattern="^(Topic|Skill)$")
    score: float
    prior_mastery: float
    confidence: Optional[float] = None

@router.post("/mastery/update", response_model=StandardResponse, responses={400: {"model": ApiError}})
async def mastery_update(req: MasteryUpdateRequest):
    res = update_mastery(req.prior_mastery, req.score, req.confidence)
    return {"items": [{"uid": req.entity_uid, "kind": req.kind, **res}], "meta": {}}
