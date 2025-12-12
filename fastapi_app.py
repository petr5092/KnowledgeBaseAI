"""KnowledgeBaseAI FastAPI

Основной API-сервис для взаимодействия с графом знаний и персонализацией.

Ключевые возможности:
- Глобальные и персональные веса тем/навыков (static/dynamic/user-specific)
- Построение дорожных карт обучения (глобальная и пользовательская)
- Обновление прогресса пользователя и пересчёт адаптивных связей методов
- Доступ к уровням знания, фиксация завершений, базовые интеграции с БД/Neo4j

Архитектурные заметки:
- Веса и связи хранятся в Neo4j; пользовательские веса не изменяют первичные данные
- OLTP операции вынесены в отдельные эндпоинты (см. секцию /oltp/*)
- Админ-операции защищены API-ключом через заголовок X-API-Key
"""
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
    compute_topic_user_weight,
    compute_skill_user_weight,
    knowledge_level_from_weight,
    build_user_roadmap_stateless,
)
from services.question_selector import select_examples_for_topics, all_topic_uids_from_examples
from kb_jobs import start_rebuild_async, get_job_status

app = FastAPI(
    title="KnowledgeBaseAI API",
    description=(
        "Единая база знаний (Neo4j) с персонализацией."
        "\nГлобальные статичные веса и динамичные веса; пользовательские веса не изменяют первичные данные."
        "\nЭндпоинты поддерживают глобальные и персональные сценарии обучения."
    ),
    version="1.0.0",
)


class TopicTestInput(BaseModel):
    topic_uid: str
    score: float
    base_weight: float | None = None


class SkillTestInput(BaseModel):
    skill_uid: str
    score: float
    base_weight: float | None = None


class RoadmapRequest(BaseModel):
    """Запрос глобальной дорожной карты: subject_uid (опционально) и лимит результатов."""
    subject_uid: str | None = None
    limit: int = 50


@app.on_event("startup")
def startup_event():
    """Инициализация приложения: выставление значений по умолчанию для весов узлов в графе (при наличии Neo4j)."""
    try:
        driver = get_driver()
        with driver.session() as session:
            ensure_weight_defaults(session)
        driver.close()
    except Exception:
        pass


def require_api_key(x_api_key: str | None) -> None:
    """Проверка админ-ключа для защищённых операций."""
    import os
    expected = os.getenv('ADMIN_API_KEY')
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.post("/test_result")
def test_result(payload: TopicTestInput) -> Dict:
    return compute_topic_user_weight(
        topic_uid=payload.topic_uid,
        score=payload.score,
        base_weight=payload.base_weight,
    )


@app.post("/skill_test_result")
def skill_test_result(payload: SkillTestInput) -> Dict:
    return compute_skill_user_weight(
        skill_uid=payload.skill_uid,
        score=payload.score,
        base_weight=payload.base_weight,
    )


@app.get("/knowledge_level/{topic_uid}", summary="Уровень знаний по теме (глобально)", description=(
    "Возвращает статичный и динамичный вес темы в глобальном графе."
    "\nИспользуется для агрегированного обзора без персонализации."
))
def get_knowledge_level(topic_uid: str) -> Dict:
    """Вернуть статичный/динамичный вес темы в глобальном графе."""
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
    """Вернуть статичный/динамичный вес навыка в глобальном графе."""
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


class LevelRequest(BaseModel):
    weight: float

@app.post("/user/topic_level")
def user_topic_level(payload: LevelRequest) -> Dict:
    return {"level": knowledge_level_from_weight(payload.weight)}


@app.post("/user/skill_level")
def user_skill_level(payload: LevelRequest) -> Dict:
    return {"level": knowledge_level_from_weight(payload.weight)}


class AdaptiveTestRequest(BaseModel):
    subject_uid: str | None = None
    topic_weights: Dict[str, float] = {}
    skill_weights: Dict[str, float] = {}
    question_count: int = 10
    difficulty_min: int = 1
    difficulty_max: int = 5
    exclude_question_uids: List[str] = []


class UserRoadmapRequest(BaseModel):
    subject_uid: str | None = None
    topic_weights: Dict[str, float] = {}
    skill_weights: Dict[str, float] = {}
    limit: int = 50
    penalty_factor: float = 0.15

@app.post("/user/roadmap")
def user_roadmap(payload: UserRoadmapRequest) -> Dict:
    items = build_user_roadmap_stateless(
        subject_uid=payload.subject_uid,
        user_topic_weights=payload.topic_weights,
        user_skill_weights=payload.skill_weights,
        limit=payload.limit,
        penalty_factor=payload.penalty_factor,
    )
    return {"roadmap": items}


class CompleteTopicRequest(BaseModel):
    """Пейлоад фиксации завершения темы пользователем."""
    user_id: str
    topic_uid: str
    time_spent_sec: float
    errors: int = 0


@app.post("/user/complete_topic")
def api_complete_topic(payload: CompleteTopicRequest) -> Dict:
    return {"ok": True, "stored": False}


class CompleteSkillRequest(BaseModel):
    """Пейлоад фиксации завершения навыка пользователем."""
    user_id: str
    skill_uid: str
    time_spent_sec: float
    errors: int = 0


@app.post("/user/complete_skill")
def api_complete_skill(payload: CompleteSkillRequest) -> Dict:
    return {"ok": True, "stored": False}

@app.post("/adaptive/questions")
def get_adaptive_questions(payload: AdaptiveTestRequest) -> Dict:
    roadmap = build_user_roadmap_stateless(
        subject_uid=payload.subject_uid,
        user_topic_weights=payload.topic_weights,
        user_skill_weights=payload.skill_weights,
        limit=payload.question_count * 3,
    )
    topic_uids = [t["topic_uid"] for t in roadmap] or all_topic_uids_from_examples()
    examples = select_examples_for_topics(
        topic_uids=topic_uids,
        limit=payload.question_count,
        difficulty_min=payload.difficulty_min,
        difficulty_max=payload.difficulty_max,
        exclude_uids=set(payload.exclude_question_uids),
    )
    return {"questions": examples}

@app.post("/kb/rebuild_async")
def kb_rebuild_async() -> Dict:
    return start_rebuild_async()

@app.get("/kb/rebuild_status")
def kb_rebuild_status(job_id: str) -> Dict:
    return get_job_status(job_id)


@app.post("/recompute_links", summary="Пересчитать adaptive_weight на связях LINKED", description=(
    "Пересчитывает свойство adaptive_weight для всех связей Skill-[:LINKED]->Method"
    " на основе текущих динамичных весов навыков (глобально или после обновлений пользователя)."
))
def recompute_links(x_api_key: str | None = Header(default=None)) -> Dict:
    """Пересчитать adaptive_weight для всех связей Skill→Method на основе актуальных динамичных весов."""
    try:
        require_api_key(x_api_key)
        stats = recompute_relationship_weights()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
