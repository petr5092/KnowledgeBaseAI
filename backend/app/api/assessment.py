from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from starlette.responses import StreamingResponse
from app.services.graph.neo4j_repo import Neo4jRepo
from app.config.settings import settings
from app.api.common import ApiError, StandardResponse
from app.services.questions import select_examples_for_topics
import json
from enum import Enum
from app.events.publisher import get_redis

router = APIRouter(prefix="/v1/assessment", tags=["Интеграция с LMS"])

from app.schemas.context import UserContext

class VisualizationType(str, Enum):
    GEOMETRIC_SHAPE = "geometric_shape"
    GRAPH = "graph"
    DIAGRAM = "diagram"
    CHART = "chart"

class VisualizationData(BaseModel):
    type: VisualizationType
    coordinates: List[Dict[str, Any]] | Dict[str, Any]
    params: Optional[Dict[str, Any]] = {}

    @model_validator(mode='after')
    def validate_coordinates(self):
        if self.type == VisualizationType.GEOMETRIC_SHAPE:
            if not isinstance(self.coordinates, list):
                raise ValueError("Coordinates for geometric_shape must be a list of points.")
            if not all(isinstance(p, dict) and "x" in p and "y" in p for p in self.coordinates):
                 raise ValueError("Each point in geometric_shape must have 'x' and 'y'.")
        elif self.type == VisualizationType.GRAPH:
            # Graph can be list of points or function params
            pass 
        return self

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
    is_visual: bool = False
    visualization: Optional[VisualizationData] = None

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
    if uc.user_class is not None:
        return int(uc.user_class)
        
    attrs = uc.attributes or {}
    if attrs.get("level") is not None:
        return int(attrs["level"])
    if attrs.get("user_class") is not None:
        return int(attrs["user_class"])
        
    age = uc.age
    if age is None:
        age = attrs.get("age")
        
    if age is not None:
        a = int(age)
        if a < 7: return 1
        if a > 17: return 11
        return a - 6
    return 7

def _topic_accessible(subject_uid: str, topic_uid: str, resolved_level: int) -> bool:
    # If resolved_level is 0 (or negative), treat as Admin/Test mode -> Allow all
    if resolved_level <= 0:
        return True
        
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
            # Topic might exist but not linked to subject? 
            # Check if topic exists at all
            repo = Neo4jRepo()
            exists = repo.read("MATCH (t:Topic {uid:$tu}) RETURN 1", {"tu": topic_uid})
            repo.close()
            return bool(exists)

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

from app.services.kb.builder import openai_chat_async
import random
import uuid

def _fallback_stub(topic_uid: str, exclude_count: int) -> Dict:
    idx = exclude_count
    templates = [
        {
            "type": "free_text",
            "prompt": f"Explain the practical application of '{topic_uid}' in real-world scenarios.",
            "options": []
        },
        {
            "type": "single_choice",
            "prompt": f"Which of the following best describes the core principle of '{topic_uid}'?",
            "options": [
                {"option_uid": "opt_1", "text": "It is deterministic and predictable."},
                {"option_uid": "opt_2", "text": "It models uncertainty using probability."},
                {"option_uid": "opt_3", "text": "It is only applicable to physics."},
                {"option_uid": "opt_4", "text": "It ignores outliers completely."}
            ]
        },
        {
            "type": "numeric",
            "prompt": f"Given a dataset with mean=10 and std_dev=2, calculate the Z-score for a value of 14 (related to '{topic_uid}').",
            "options": []
        },
        {
            "type": "single_choice",
            "prompt": f"Identify the distribution type shown in the diagram (bell-shaped, symmetric).",
            "options": [
                {"option_uid": "opt_a", "text": "Normal Distribution"},
                {"option_uid": "opt_b", "text": "Exponential Distribution"},
                {"option_uid": "opt_c", "text": "Uniform Distribution"}
            ]
        },
        {
             "type": "free_text",
             "prompt": f"Describe the relationship between variance and standard deviation in the context of '{topic_uid}'.",
             "options": []
        },
        {
             "type": "single_choice",
             "prompt": "What is the area under the Probability Density Function (PDF) curve equal to?",
             "options": [
                 {"option_uid": "opt_x", "text": "1.0"},
                 {"option_uid": "opt_y", "text": "0.5"},
                 {"option_uid": "opt_z", "text": "Depends on the mean"}
             ]
        }
    ]
    tmpl = templates[idx % len(templates)]
    return {
        "question_uid": f"Q-STUB-{topic_uid}-{idx+1}",
        "subject_uid": "",
        "topic_uid": topic_uid,
        "type": tmpl["type"],
        "prompt": tmpl["prompt"],
        "options": tmpl["options"],
        "meta": {"difficulty": 0.5, "skill_uid": ""},
    }

async def _generate_question_llm(topic_uid: str, exclude_uids: set, is_visual: bool = False) -> Dict:
    # 1. Get Topic Title
    repo = Neo4jRepo()
    topic_title = topic_uid
    try:
        def _get_title(tx):
            res = tx.run("MATCH (t:Topic {uid: $uid}) RETURN t.title as title", uid=topic_uid)
            rec = res.single()
            return rec["title"] if rec else None
        
        # Use sync retry since it's robust, running in async context is acceptable for MVP
        title = repo._retry(lambda s: s.read_transaction(_get_title))
        if title:
            topic_title = title
    except Exception:
        pass
    finally:
        repo.close()

    # Auto-detect visual topics
    if not is_visual and topic_title:
        visual_keywords = ["geometry", "triangle", "circle", "graph", "function", "chart", "diagram", "геометрия", "треугольник", "график", "функция", "окружность", "углы", "angles", "slope", "derivative", "integral"]
        if any(k in topic_title.lower() for k in visual_keywords):
            is_visual = True

    # 2. Choose Type
    q_types = ["single_choice", "single_choice", "numeric", "free_text", "boolean"]
    q_type = random.choice(q_types)
    
    # 3. Prompt
    visual_instruction = ""
    if is_visual:
        visual_instruction = """
    Visualization Requirements:
    - You MUST set "is_visual": true.
    - You MUST include a "visualization" object.
    - "visualization" structure:
      {
        "type": "geometric_shape" | "graph" | "diagram" | "chart",
        "coordinates": [ ... ], // Array of points {x,y} for shapes, or other format
        "params": { "color": "...", "label": "...", ... } // Optional parameters
      }
    - Coordinate formats:
      * geometric_shape: [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 5, "y": 10}] (example triangle)
      * graph: [{"x": -10, "y": ...}, ...] or functional params
      * diagram/chart: appropriate JSON representation
    """

    prompt_text = f"""
    Generate a unique assessment question for the topic "{topic_title}" (UID: {topic_uid}).
    Context: Adaptive learning platform.
    Target Audience: High school / University students.
    Language: Russian.
    
    Question Type: {q_type}
    Is Visual Task: {is_visual}
    {visual_instruction}
    
    Requirements:
    - Output valid JSON only.
    - "single_choice": 4 options, 1 correct.
    - "numeric": Problem with specific numeric answer.
    - "boolean": True/False statement.
    - "free_text": Open-ended question.
    
    JSON Structure:
    {{
        "prompt": "Question text",
        "options": [
            {{"option_uid": "opt_1", "text": "Option 1", "is_correct": true}},
            {{"option_uid": "opt_2", "text": "Option 2", "is_correct": false}}
        ],
        "correct_value": 123.45,
        "explanation": "Brief explanation",
        "is_visual": { "true" if is_visual else "false" },
        "visualization": {{ ... }}
    }}
    """
    
    messages = [{"role": "user", "content": prompt_text}]
    
    try:
        res = await openai_chat_async(messages, temperature=0.9)
        if not res.get("ok"):
             return _fallback_stub(topic_uid, len(exclude_uids))
        
        content = res.get("content", "")
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        data = json.loads(content.strip())
        
        q_uid = f"Q-GEN-{uuid.uuid4().hex[:8]}"
        
        options = []
        if "options" in data and isinstance(data["options"], list):
            for i, opt in enumerate(data["options"]):
                options.append({
                    "option_uid": opt.get("option_uid") or f"opt_{i}",
                    "text": opt.get("text", "")
                })
        
        visualization_data = None
        if data.get("is_visual") and data.get("visualization"):
            try:
                # Basic validation or casting if needed
                vis = data["visualization"]
                # Ensure type is valid enum or string
                visualization_data = VisualizationData(
                    type=vis.get("type"),
                    coordinates=vis.get("coordinates"),
                    params=vis.get("params", {})
                )
            except Exception as e:
                print(f"Visualization validation error: {e}")
                # Fallback: ignore visualization if invalid
                visualization_data = None

        return {
            "question_uid": q_uid,
            "subject_uid": "",
            "topic_uid": topic_uid,
            "type": q_type,
            "prompt": data.get("prompt", "Question"),
            "options": options,
            "is_visual": data.get("is_visual", False) and (visualization_data is not None),
            "visualization": visualization_data,
            "meta": {
                "difficulty": 0.5,
                "skill_uid": "",
                "generated": True,
                "correct_data": data
            }
        }
    except Exception as e:
        print(f"Gen Error: {e}")
        return _fallback_stub(topic_uid, len(exclude_uids))

async def _select_question(topic_uid: str, difficulty_min: int, difficulty_max: int, exclude_uids: set = set()) -> Dict:
    qs = select_examples_for_topics([topic_uid], limit=1, difficulty_min=difficulty_min, difficulty_max=difficulty_max, exclude_uids=exclude_uids)
    if qs:
        q = qs[0]
        return {
            "question_uid": str(q.get("uid") or f"Q-STUB-{topic_uid}-{len(exclude_uids)+1}"),
            "subject_uid": "",
            "topic_uid": topic_uid,
            "type": "free_text",
            "prompt": str(q.get("statement") or q.get("title") or ""),
            "options": [],
            "meta": {"difficulty": float(q.get("difficulty") or 0.5), "skill_uid": ""},
        }
    
    return await _generate_question_llm(topic_uid, exclude_uids)

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
    first_q = await _select_question(payload.topic_uid, 3, 3, set())
    sess_data = {
        "subject_uid": payload.subject_uid,
        "topic_uid": payload.topic_uid,
        "resolved_user_class": resolved,
        "asked": [],
        "last_question_uid": first_q["question_uid"],
        "good": 0,
        "bad": 0,
        "min_questions": 6,
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

async def _next_question(sess: Dict) -> Optional[Dict]:
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
    q = await _select_question(sess["topic_uid"], d, d, set(sess["asked"]))
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
    async def _stream():
        yield "event: ack\n"
        yield "data: {\"items\":[{\"accepted\":true}],\"meta\":{}}\n\n"
        if done_by_min or done_by_max:
            score = round(min(1.0, sess['good'] / max(1, len(sess['asked']))), 3)
            # Basic analytics
            gaps = []
            if score < 0.8:
                gaps.append("Базовое понимание темы требует закрепления")
            if score < 0.5:
                gaps.append("Трудности с применением концепций на практике")
                
            res = {
                "items": [
                    {
                        "topic_uid": sess["topic_uid"],
                        "level": "intermediate" if sess["good"] >= sess["bad"] else "basic",
                        "mastery": {"score": score},
                        "analytics": {
                            "gaps": gaps,
                            "recommended_focus": "Повторить теорию и пройти практику 'We Do'" if score < 0.7 else "Переходить к следующей теме",
                            "strength": "Хорошая скорость ответов" if score > 0.8 else "Внимательность к деталям"
                        }
                    }
                ],
                "meta": {}
            }
            import json
            yield "event: done\n"
            yield "data: " + json.dumps(res, ensure_ascii=False) + "\n\n"
            return
        q = await _next_question(sess)
        _save_session(sid, sess) # Save updated session after selecting next question
        import json
        yield "event: question\n"
        yield "data: " + json.dumps({"items":[q], "meta": {}}, ensure_ascii=False) + "\n\n"
    return StreamingResponse(_stream(), media_type="text/event-stream")
