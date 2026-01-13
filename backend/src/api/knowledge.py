from typing import Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.services.graph.neo4j_repo import Neo4jRepo
from src.config.settings import settings
from src.api.common import ApiError, StandardResponse
from src.services.questions import all_topic_uids_from_examples

router = APIRouter(prefix="/v1/knowledge", tags=["Интеграция с LMS"])

class UserContext(BaseModel):
    user_class: Optional[int] = None
    age: Optional[int] = None

class TopicsAvailableRequest(BaseModel):
    subject_uid: Optional[str] = None
    subject_title: Optional[str] = None
    user_context: UserContext

class TopicItem(BaseModel):
    topic_uid: str
    title: Optional[str] = None
    user_class_min: Optional[int] = None
    user_class_max: Optional[int] = None
    difficulty_band: Optional[str] = None
    prereq_topic_uids: List[str] = []

class TopicsAvailableResponse(BaseModel):
    subject_uid: str
    resolved_user_class: int
    topics: List[TopicItem]

def _age_to_class(age: Optional[int]) -> int:
    if age is None:
        return 7
    a = int(age)
    if a < 7:
        return 1
    if a > 17:
        return 11
    return a - 6

@router.post(
    "/topics/available",
    responses={400: {"model": ApiError}},
    response_model=StandardResponse,
)
async def topics_available(payload: TopicsAvailableRequest) -> Dict:
    uc = payload.user_context or UserContext()
    resolved = int(uc.user_class) if uc.user_class is not None else _age_to_class(uc.age)
    topics: List[Dict] = []
    su = payload.subject_uid
    if not su and (payload.subject_title or "").strip():
        try:
            repo = Neo4jRepo()
            r = repo.read("MATCH (sub:Subject) WHERE toUpper(sub.title)=toUpper($t) RETURN sub.uid AS uid LIMIT 1", {"t": payload.subject_title})
            su = r[0]["uid"] if r else None
            repo.close()
        except Exception:
            su = None
    if settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password.get_secret_value():
        try:
            repo = Neo4jRepo()
            rows = repo.read(
                (
                    "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
                    "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       collect(pre.uid) AS prereq_topic_uids"
                ),
                {"su": su},
            )
            for r in rows:
                mn = r.get("user_class_min")
                mx = r.get("user_class_max")
                ok = True
                if isinstance(mn, (int, float)):
                    ok = ok and resolved >= int(mn)
                if isinstance(mx, (int, float)):
                    ok = ok and resolved <= int(mx)
                if ok:
                    topics.append(
                        {
                            "topic_uid": r.get("topic_uid"),
                            "title": r.get("title"),
                            "user_class_min": int(mn) if isinstance(mn, (int, float)) else None,
                            "user_class_max": int(mx) if isinstance(mx, (int, float)) else None,
                            "difficulty_band": r.get("difficulty_band") or "standard",
                            "prereq_topic_uids": [p for p in (r.get("prereq_topic_uids") or []) if p],
                        }
                    )
            repo.close()
        except Exception:
            topics = []
    if not topics:
        for tu in all_topic_uids_from_examples():
            topics.append(
                {
                    "topic_uid": tu,
                    "title": tu,
                    "user_class_min": None,
                    "user_class_max": None,
                    "difficulty_band": "standard",
                    "prereq_topic_uids": [],
                }
            )
    return {"items": topics, "meta": {"subject_uid": su or payload.subject_uid, "resolved_user_class": resolved}}
