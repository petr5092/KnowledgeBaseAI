import os
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

from neo4j_utils import (
    update_dynamic_weight,
    update_skill_dynamic_weight,
    get_current_knowledge_level,
    get_current_skill_level,
    build_adaptive_roadmap,
    get_driver,
    ensure_weight_defaults,
    recompute_relationship_weights,
    update_user_topic_weight,
    update_user_skill_weight,
    get_user_topic_level,
    get_user_skill_level,
    build_user_roadmap,
)

app = FastAPI(
    title="KnowledgeBaseAI API",
    description=(
        "Единая база знаний (Neo4j) с персонализацией."
        "\nГлобальные статичные веса и динамичные веса; пользовательские веса не изменяют первичные данные."
        "\nЭндпоинты поддерживают глобальные и персональные сценарии обучения."
    ),
    version="1.0.0",
)


class TestResult(BaseModel):
    topic_uid: str
    score: float
    user_id: str | None = None


class SkillTestResult(BaseModel):
    skill_uid: str
    score: float
    user_id: str | None = None


class RoadmapRequest(BaseModel):
    subject_uid: str | None = None
    limit: int = 50


@app.on_event("startup")
def startup_event():
    driver = get_driver()
    with driver.session() as session:
        ensure_weight_defaults(session)
    driver.close()


def require_api_key(x_api_key: str | None) -> None:
    import os
    expected = os.getenv('ADMIN_API_KEY')
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.post("/test_result", summary="Обновить результат теста темы", description=(
    "Обновляет динамичный вес темы."
    "\nЕсли передан user_id — обновляет пользовательскую связь User-[:PROGRESS_TOPIC]->Topic;"
    " иначе — глобальный dynamic_weight темы."
    "\nПосле обновления пересчитывает adaptive_weight на связях Skill-[:LINKED]->Method."
))
def submit_test_result(payload: TestResult) -> Dict:
    try:
        if payload.user_id:
            updated = update_user_topic_weight(payload.user_id, payload.topic_uid, payload.score)
        else:
            updated = update_dynamic_weight(payload.topic_uid, payload.score)
        stats = recompute_relationship_weights()
        return {"ok": True, "updated": updated, "recomputed": stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/skill_test_result", summary="Обновить результат теста навыка", description=(
    "Обновляет динамичный вес навыка."
    "\nЕсли передан user_id — обновляет пользовательскую связь User-[:PROGRESS_SKILL]->Skill;"
    " иначе — глобальный dynamic_weight навыка."
    "\nПосле обновления пересчитывает adaptive_weight на связях Skill-[:LINKED]->Method."
))
def submit_skill_test_result(payload: SkillTestResult) -> Dict:
    try:
        if payload.user_id:
            updated = update_user_skill_weight(payload.user_id, payload.skill_uid, payload.score)
        else:
            updated = update_skill_dynamic_weight(payload.skill_uid, payload.score)
        stats = recompute_relationship_weights()
        return {"ok": True, "updated": updated, "recomputed": stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/knowledge_level/{topic_uid}", summary="Уровень знаний по теме (глобально)", description=(
    "Возвращает статичный и динамичный вес темы в глобальном графе."
    "\nИспользуется для агрегированного обзора без персонализации."
))
def get_knowledge_level(topic_uid: str) -> Dict:
    try:
        lvl = get_current_knowledge_level(topic_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/skill_level/{skill_uid}", summary="Уровень по навыку (глобально)", description=(
    "Возвращает статичный и динамичный вес навыка в глобальном графе."
    "\nИспользуется для агрегированного обзора без персонализации."
))
def get_skill_level(skill_uid: str) -> Dict:
    try:
        lvl = get_current_skill_level(skill_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/roadmap", summary="Глобальная дорожная карта обучения", description=(
    "Строит список тем, навыков и методов, отсортированный по глобальному dynamic_weight темы."
    "\nПараметры: subject_uid (опционально ограничивает предмет), limit (ограничение размера)."
))
def get_roadmap(payload: RoadmapRequest) -> Dict:
    try:
        items = build_adaptive_roadmap(payload.subject_uid, payload.limit)
        return {"ok": True, "roadmap": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/user/knowledge_level/{user_id}/{topic_uid}", summary="Уровень пользователя по теме", description=(
    "Возвращает статичный вес темы и персональный dynamic_weight пользователя по теме"
    " (если нет пользовательской записи, используется глобальный dynamic_weight/статичный вес)."
))
def get_user_knowledge_level(user_id: str, topic_uid: str) -> Dict:
    try:
        lvl = get_user_topic_level(user_id, topic_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/user/skill_level/{user_id}/{skill_uid}", summary="Уровень пользователя по навыку", description=(
    "Возвращает статичный вес навыка и персональный dynamic_weight пользователя по навыку"
    " (если нет пользовательской записи, используется глобальный dynamic_weight/статичный вес)."
))
def get_user_skill_level(user_id: str, skill_uid: str) -> Dict:
    try:
        lvl = get_user_skill_level(user_id, skill_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


class UserRoadmapRequest(BaseModel):
    user_id: str
    subject_uid: str | None = None
    limit: int = 50
    penalty_factor: float | None = 0.15


@app.post("/user/roadmap", summary="Персональная дорожная карта обучения", description=(
    "Строит дорожную карту для пользователя: темы сортируются по персональному dynamic_weight."
    "\nВозвращает темы с приоритетами, связанные навыки/методы с учетом пользовательских весов."
))
def get_user_roadmap(payload: UserRoadmapRequest) -> Dict:
    try:
        items = build_user_roadmap(payload.user_id, payload.subject_uid, payload.limit, payload.penalty_factor or 0.15)
        return {"ok": True, "roadmap": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CompleteTopicRequest(BaseModel):
    user_id: str
    topic_uid: str
    time_spent_sec: float
    errors: int = 0


@app.post("/user/complete_topic", summary="Зафиксировать завершение темы", description=(
    "Создаёт связь User-[:COMPLETED]->Topic с метриками времени и ошибок."
))
def api_complete_topic(payload: CompleteTopicRequest) -> Dict:
    try:
        return complete_user_topic(payload.user_id, payload.topic_uid, payload.time_spent_sec, payload.errors)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CompleteSkillRequest(BaseModel):
    user_id: str
    skill_uid: str
    time_spent_sec: float
    errors: int = 0


@app.post("/user/complete_skill", summary="Зафиксировать завершение навыка", description=(
    "Создаёт связь User-[:COMPLETED]->Skill с метриками времени и ошибок."
))
def api_complete_skill(payload: CompleteSkillRequest) -> Dict:
    try:
        return complete_user_skill(payload.user_id, payload.skill_uid, payload.time_spent_sec, payload.errors)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/recompute_links", summary="Пересчитать adaptive_weight на связях LINKED", description=(
    "Пересчитывает свойство adaptive_weight для всех связей Skill-[:LINKED]->Method"
    " на основе текущих динамичных весов навыков (глобально или после обновлений пользователя)."
))
def recompute_links(x_api_key: str | None = Header(default=None)) -> Dict:
    try:
        require_api_key(x_api_key)
        stats = recompute_relationship_weights()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
