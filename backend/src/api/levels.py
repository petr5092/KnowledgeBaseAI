from fastapi import APIRouter
from typing import Dict
from src.services.graph.utils import get_user_topic_level, get_user_skill_level

router = APIRouter(prefix="/v1/levels", tags=["Уровни"])

@router.get("/topic/{uid}", summary="Уровень темы", description="Возвращает уровень освоения темы для статeless-пользователя.")
async def level_topic(uid: str) -> Dict:
    """
    Принимает:
      - uid: UID темы

    Возвращает:
      - объект уровня навыка/темы согласно алгоритму get_user_topic_level
    """
    return get_user_topic_level(user_id="stateless", topic_uid=uid)

@router.get("/skill/{uid}", summary="Уровень навыка", description="Возвращает уровень освоения навыка для статeless-пользователя.")
async def level_skill(uid: str) -> Dict:
    """
    Принимает:
      - uid: UID навыка

    Возвращает:
      - объект уровня навыка согласно алгоритму get_user_skill_level
    """
    return get_user_skill_level(user_id="stateless", skill_uid=uid)
