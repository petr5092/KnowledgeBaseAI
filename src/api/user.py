from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict
from src.services.graph.utils import compute_topic_user_weight, compute_skill_user_weight
from src.services.roadmap_planner import plan_route

router = APIRouter(prefix="/v1/user")

class ComputeTopicInput(BaseModel):
    topic_uid: str
    score: float
    base_weight: float | None = None

@router.post("/compute_topic_weight")
async def compute_topic_weight(payload: ComputeTopicInput) -> Dict:
    return compute_topic_user_weight(topic_uid=payload.topic_uid, score=payload.score, base_weight=payload.base_weight)

class ComputeSkillInput(BaseModel):
    skill_uid: str
    score: float
    base_weight: float | None = None

@router.post("/compute_skill_weight")
async def compute_skill_weight(payload: ComputeSkillInput) -> Dict:
    return compute_skill_user_weight(skill_uid=payload.skill_uid, score=payload.score, base_weight=payload.base_weight)

class UserRoadmapInput(BaseModel):
    subject_uid: str | None = None
    progress: Dict[str, float] = {}
    limit: int = 50

@router.post("/roadmap")
async def user_roadmap(payload: UserRoadmapInput) -> Dict:
    items = plan_route(payload.subject_uid, payload.progress, limit=payload.limit)
    return {"roadmap": items}
