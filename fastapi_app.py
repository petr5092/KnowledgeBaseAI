import os
from typing import List, Dict
from fastapi import FastAPI, HTTPException
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

app = FastAPI()


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


@app.post("/test_result")
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


@app.post("/skill_test_result")
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


@app.get("/knowledge_level/{topic_uid}")
def get_knowledge_level(topic_uid: str) -> Dict:
    try:
        lvl = get_current_knowledge_level(topic_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/skill_level/{skill_uid}")
def get_skill_level(skill_uid: str) -> Dict:
    try:
        lvl = get_current_skill_level(skill_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/roadmap")
def get_roadmap(payload: RoadmapRequest) -> Dict:
    try:
        items = build_adaptive_roadmap(payload.subject_uid, payload.limit)
        return {"ok": True, "roadmap": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/user/knowledge_level/{user_id}/{topic_uid}")
def get_user_knowledge_level(user_id: str, topic_uid: str) -> Dict:
    try:
        lvl = get_user_topic_level(user_id, topic_uid)
        return {"ok": True, "level": lvl}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/user/skill_level/{user_id}/{skill_uid}")
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


@app.post("/user/roadmap")
def get_user_roadmap(payload: UserRoadmapRequest) -> Dict:
    try:
        items = build_user_roadmap(payload.user_id, payload.subject_uid, payload.limit)
        return {"ok": True, "roadmap": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/recompute_links")
def recompute_links() -> Dict:
    try:
        stats = recompute_relationship_weights()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
