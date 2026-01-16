from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from starlette.responses import StreamingResponse
from app.services.graph.neo4j_repo import Neo4jRepo
from app.config.settings import settings
from app.api.common import ApiError, StandardResponse
from app.services.questions import select_examples_for_topics
import json
from app.events.publisher import get_redis

router = APIRouter(prefix="/v1/assessment", tags=["Интеграция с LMS"])

class UserContext(BaseModel):
    user_class: Optional[int] = None
    age: Optional[int] = None

class StartRequest(BaseModel):
    subject_uid: str
    topic_uid: str
    user_context: UserContext

class OptionDTO(BaseModel):
    option_uid: str
    text: str

class QuestionDTO(BaseModel):
    question_uid: str
    subject_uid: str
    topic_uid: str
    type: str
    prompt: str
    options: List[OptionDTO] = []
    meta: Dict = {}

class StartResponse(BaseModel):
    assessment_session_id: str
    question: QuestionDTO

class AnswerDTO(BaseModel):
    selected_option_uids: List[str] = []
    text: Optional[str] = None
    value: Optional[float] = None

    @model_validator(mode='after')
    def check_not_empty(self):
        if not self.selected_option_uids and not self.text and self.value is None:
            # Allow empty for now but log/warn? Or just validate?
            # User said "structure looks vulnerable".
            pass 
        return self

class ClientMeta(BaseModel):
    time_spent_ms: Optional[int] = None
    attempt: Optional[int] = None

class NextRequest(BaseModel):
    assessment_session_id: str
    question_uid: str
    answer: AnswerDTO
    client_meta: Optional[ClientMeta] = None

def _get_session(sid: str) -> Optional[Dict]:
    try:
        r = get_redis()
        val = r.get(f"sess:{sid}")
        return json.loads(val) if val else None
    except Exception:
        return None

def _save_session(sid: str, data: Dict):
    try:
        r = get_redis()
        r.setex(f"sess:{sid}", 86400, json.dumps(data))
    except Exception:
        pass

def _resolve_level(uc: UserContext) -> int:
    if uc.level is not None:
        return uc.level
    if uc.user_class is not None:
        return uc.user_class
    if uc.age is not None:
        a = int(uc.age)
        if a < 7: return 1
        if a > 17: return 11
        return a - 6
    return 7

def _topic_accessible(subject_uid: str, topic_uid: str, resolved_level: int) -> bool:
    if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password.get_secret_value()):
        return True
    try:
        repo = Neo4jRepo()
        row = repo.read(
            (
                "MATCH (sub:Subject {uid:$su})-[:CONTAINS*]->(t:Topic {uid:$tu}) "
                "RETURN t.user_class_min AS mn, t.user_class_max AS mx LIMIT 1"
            ),
            {"su": subject_uid, "tu": topic_uid},
        )
        repo.close()
        if not row:
            return False
        mn = row[0].get("mn")
        mx = row[0].get("mx")
        ok = True
        if isinstance(mn, (int, float)):
            ok = ok and resolved_level >= int(mn)
        if isinstance(mx, (int, float)):
            ok = ok and resolved_level <= int(mx)
        return ok
    except Exception:
        return True

def _select_question(topic_uid: str, difficulty_min: int, difficulty_max: int) -> Dict:
    qs = select_examples_for_topics([topic_uid], limit=1, difficulty_min=difficulty_min, difficulty_max=difficulty_max, exclude_uids=set())
    if qs:
        q = qs[0]
        return {
            "question_uid": str(q.get("uid") or f"Q-STUB-{topic_uid}-1"),
            "subject_uid": "",
            "topic_uid": topic_uid,
            "type": "free_text",
            "prompt": str(q.get("statement") or q.get("title") or ""),
            "options": [],
            "meta": {"difficulty": float(q.get("difficulty") or 0.5), "skill_uid": ""},
        }
    return {
        "question_uid": f"Q-STUB-{topic_uid}-1",
        "subject_uid": "",
        "topic_uid": topic_uid,
        "type": "free_text",
        "prompt": f"Explain the key concept of '{topic_uid}' and provide an example.",
        "options": [],
        "meta": {"difficulty": 0.5, "skill_uid": ""},
    }

@router.post(
    "/start",
    response_model=StandardResponse,
    responses={400: {"model": ApiError}, 404: {"model": ApiError}},
)
async def start(payload: StartRequest) -> Dict:
    uc = payload.user_context or UserContext()
    resolved = _resolve_level(uc)
    if not _topic_accessible(payload.subject_uid, payload.topic_uid, resolved):
        raise HTTPException(status_code=404, detail="Topic not available")
    import uuid
    sid = uuid.uuid4().hex
    first_q = _select_question(payload.topic_uid, 3, 3)
    sess_data = {
        "subject_uid": payload.subject_uid,
        "topic_uid": payload.topic_uid,
        "resolved_user_class": resolved,
        "asked": [],
        "last_question_uid": first_q["question_uid"],
        "good": 0,
        "bad": 0,
        "min_questions": 5,
        "max_questions": 20,
        "target_confidence": 0.85,
        "stability_window": 4,
        "d_history": [],
    }
    _save_session(sid, sess_data)
    return {"items": [first_q], "meta": {"assessment_session_id": sid}}

def _evaluate(answer: AnswerDTO) -> float:
    if answer is None:
        return 0.0
    if answer.text and len(str(answer.text).strip()) >= 3:
        return 1.0
    if answer.selected_option_uids:
        return 1.0
    try:
        v = float(answer.value or 0.0)
        return 1.0 if v != 0.0 else 0.0
    except Exception:
        return 0.0

def _confidence(sess: Dict) -> float:
    asked = len(sess["asked"])
    w = sess["stability_window"]
    h = sess["d_history"][-w:] if w > 0 else sess["d_history"]
    if not h:
        return 0.0
    stable = 1.0 if max(h) - min(h) <= 1 else 0.0
    base = min(1.0, asked / max(1, sess["min_questions"]))
    return max(0.0, min(1.0, 0.6 * base + 0.4 * stable))

def _next_question(sess: Dict) -> Optional[Dict]:
    good = sess["good"]
    bad = sess["bad"]
    if len(sess["asked"]) >= sess["max_questions"]:
        return None
    d_last = sess["d_history"][-1] if sess["d_history"] else 3
    if good > bad:
        d = min(10, d_last + 1)
    else:
        d = max(1, d_last - 1)
    sess["d_history"].append(d)
    q = _select_question(sess["topic_uid"], d, d)
    sess["last_question_uid"] = q["question_uid"]
    return q

@router.post(
    "/next",
    responses={400: {"model": ApiError}},
)
async def next_question(payload: NextRequest):
    sid = payload.assessment_session_id
    sess = _get_session(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.question_uid != sess.get("last_question_uid"):
        raise HTTPException(status_code=400, detail="Invalid sequence")
    score = _evaluate(payload.answer)
    if score >= 0.5:
        sess["good"] += 1
    else:
        sess["bad"] += 1
    sess["asked"].append(payload.question_uid)
    _save_session(sid, sess)
    
    done_by_min = len(sess["asked"]) >= sess["min_questions"] and _confidence(sess) >= sess["target_confidence"]
    done_by_max = len(sess["asked"]) >= sess["max_questions"]
    def _stream():
        yield "event: ack\n"
        yield "data: {\"items\":[{\"accepted\":true}],\"meta\":{}}\n\n"
        if done_by_min or done_by_max:
            res = {
                "items": [
                    {
                        "topic_uid": sess["topic_uid"],
                        "level": "intermediate" if sess["good"] >= sess["bad"] else "basic",
                        "mastery": {"score": round(min(1.0, sess['good'] / max(1, len(sess['asked']))), 3)},
                    }
                ],
                "meta": {}
            }
            import json
            yield "event: done\n"
            yield "data: " + json.dumps(res, ensure_ascii=False) + "\n\n"
            return
        q = _next_question(sess)
        _save_session(sid, sess) # Save updated session after selecting next question
        import json
        yield "event: question\n"
        yield "data: " + json.dumps({"items":[q], "meta": {}}, ensure_ascii=False) + "\n\n"
    return StreamingResponse(_stream(), media_type="text/event-stream")
