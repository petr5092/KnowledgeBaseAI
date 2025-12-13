from fastapi import APIRouter
from typing import Dict
from src.services.graph.utils import get_user_topic_level, get_user_skill_level

router = APIRouter(prefix="/v1/levels")

@router.get("/topic/{uid}")
async def level_topic(uid: str) -> Dict:
    return get_user_topic_level(user_id="stateless", topic_uid=uid)

@router.get("/skill/{uid}")
async def level_skill(uid: str) -> Dict:
    return get_user_skill_level(user_id="stateless", skill_uid=uid)
