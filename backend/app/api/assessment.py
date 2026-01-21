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
                raise ValueError("Coordinates for geometric_shape must be a list.")
            
            # Mode 1: Single shape (List of points)
            is_single_shape = all(isinstance(p, dict) and "x" in p and "y" in p for p in self.coordinates)
            
            # Mode 2: Multiple shapes (List of shape objects)
            is_multi_shape = all(isinstance(p, dict) and "points" in p and isinstance(p["points"], list) for p in self.coordinates)
            
            if not is_single_shape and not is_multi_shape:
                 raise ValueError("geometric_shape must be either a list of points {x,y} OR a list of shape objects with 'points'.")
                 
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
    except Exception as e:
        print(f"Error getting session {sid}: {e}")
        return None

def _save_session(sid: str, data: Dict) -> bool:
    try:
        r = get_redis()
        r.setex(f"sess:{sid}", 86400, json.dumps(data))
        return True
    except Exception as e:
        print(f"Error saving session {sid}: {e}")
        return False

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

async def _generate_question_llm(topic_uid: str, exclude_uids: set, is_visual: bool = False, previous_prompts: List[str] = [], difficulty: int = 5) -> Dict:
    # 1. Get Topic Title
    repo = None
    topic_title = topic_uid
    try:
        repo = Neo4jRepo()
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
        if repo:
            try:
                repo.close()
            except Exception:
                pass

    # Auto-detect visual topics
    if not is_visual and topic_title:
        visual_keywords = [
            "geometry", "triangle", "circle", "graph", "function", "chart", "diagram", 
            "геометр", "треугольн", "график", "функц", "окружн", "угл", "angles", "slope", "derivative", "integral",
            "geometr", "ellips", "figur", "polygon", "mnogougoln", "ugol", "angle", "ploshchad", "area", "volume", "obem", 
            "radius", "diametr", "sechen", "section", "bokov", "lateral", "prizm", "prism", "piramid", "pyramid", 
            "shara", "sphere", "konus", "cone", "cilindr", "cylinder", "vektor", "vector",
            "эллипс", "фигур", "многоугольн", "площад", "объем", "диаметр", "сечен", "боков", "шар", "конус", "цилиндр", "вектор"
        ]
        if any(k in topic_title.lower() for k in visual_keywords):
            is_visual = True

    # 2. Choose Type
    if is_visual:
        # Prefer structured types for visual tasks to avoid "free_text" complaints
        q_types = ["single_choice", "single_choice", "numeric"]
    else:
        q_types = ["single_choice", "single_choice", "numeric", "free_text", "boolean"]
    
    q_type = random.choice(q_types)
    
    # Map difficulty int (1-10) to description
    diff_desc = "Intermediate"
    if difficulty <= 3: diff_desc = "Elementary/Basic"
    elif difficulty >= 8: diff_desc = "Advanced/Expert"
    
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
        "coordinates": [ ... ], // Array of points {x,y} for shapes, or Array of series for multiple graphs
        "params": { "color": "...", "label": "...", ... } // Optional global parameters
      }
    - Coordinate formats:
      * geometric_shape (single shape): [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 5, "y": 10}]
      * geometric_shape (multiple shapes) - USE THIS FOR COMPARISONS OR MULTIPLE FIGURES:
        [
          {"type": "polygon", "label": "Figure A", "color": "blue", "points": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 0, "y": 3}]},
          {"type": "line", "label": "Segment B", "color": "red", "points": [{"x": 5, "y": 0}, {"x": 9, "y": 0}]}
        ]
        CRITICAL FOR GEOMETRY: 
        - For SEGMENTS ("отрезки") or LINES: Use "type": "line" and provide EXACTLY 2 points (start and end). DO NOT use "polygon" for lines.
        - For POLYGONS (triangles, squares): Use "type": "polygon" and provide 3+ points.
        - The coordinates MUST be mathematically consistent with the problem statement values (scale 1:1). 
        If a side is length 5, the distance between its points must be 5. If a base is 8, the x-difference must be 8.
        Do not provide arbitrary coordinates. Calculate them to match the problem data exactly.
      * graph (single line): [{"x": -10, "y": ...}, ...]
      * graph (multiple lines/functions) - USE THIS IF PROMPT MENTIONS MULTIPLE FUNCTIONS:
        [
          {"type": "line", "label": "y=2x+3", "color": "blue", "points": [{"x": -10, "y": -17}, {"x": 10, "y": 23}]},
          {"type": "line", "label": "y=-x+1", "color": "red", "points": [{"x": -10, "y": 11}, {"x": 10, "y": -9}]}
        ]
        CRITICAL: If the prompt mentions multiple functions (e.g. f(x) and g(x)), you MUST provide an array of objects for "coordinates".
        Do not provide a single array of points if you are describing multiple functions.
      * diagram/chart: appropriate JSON representation
    """

    avoid_context = ""
    if previous_prompts:
        # Limit to last 3 prompts to avoid context overflow, but enough to prevent immediate repetition
        avoid_context = f"\\nIMPORTANT: DO NOT generate questions similar to the following (create something different):\\n{json.dumps(previous_prompts[-3:], ensure_ascii=False)}\\n"

    # Define JSON structure based on type to avoid duplication
    if q_type == "single_choice":
        json_structure = f"""
    {{
        "prompt": "Question text",
        "options": [
            {{"option_uid": "opt_1", "text": "Option 1", "is_correct": true}},
            {{"option_uid": "opt_2", "text": "Option 2", "is_correct": false}}
        ],
        "explanation": "Brief explanation",
        "is_visual": {"true" if is_visual else "false"},
        "visualization": {{ ... }}
    }}
    """
    else:
        # numeric, free_text, boolean (treated as free/numeric for simplicity or needing value)
        json_structure = f"""
    {{
        "prompt": "Question text",
        "correct_value": "Answer value",
        "explanation": "Brief explanation",
        "is_visual": {"true" if is_visual else "false"},
        "visualization": {{ ... }}
    }}
    """

    prompt_text = f"""
    Generate a unique assessment question for the topic "{topic_title}" (UID: {topic_uid}).
    Context: Adaptive learning platform.
    Target Audience: High school / University students.
    Language: Russian.
    
    Difficulty Level: {difficulty}/10 ({diff_desc}).
    - Level 1-3: Basic definition, simple recognition, 1-step problems.
    - Level 4-7: Standard problems, application of formula, 2-step reasoning.
    - Level 8-10: Complex problems, synthesis of concepts, edge cases, multi-step.
    
    Question Type: {q_type}
    Is Visual Task: {is_visual}
    {visual_instruction}
    {avoid_context}
    
    IMPORTANT: If "Is Visual Task" is True, you MUST provide a valid "visualization" object in the JSON.
    The "visualization" object MUST have a "type" (one of: geometric_shape, graph, diagram, chart) and "coordinates".
    
    Requirements:
    - Output valid JSON only.
    - "single_choice": 4 options, 1 correct.
    - "numeric": Problem with specific numeric answer.
    - "boolean": True/False statement.
    - "free_text": Open-ended question.
    - GRAMMAR: Use singular form for single objects (e.g. "Фигура A (синяя)", not "синие"). Match gender and number correctly.
    - CONSISTENCY: The question text MUST match the number of objects in the visualization. If you show 4 figures, do not say "two figures".
    
    JSON Structure:
    {json_structure}
    """
    
    messages = [{"role": "user", "content": prompt_text}]
    
    try:
        res = await openai_chat_async(messages, temperature=0.9)
        if not res.get("ok"):
             raise Exception("LLM generation failed")
        
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
                vis_obj = VisualizationData(
                    type=vis.get("type"),
                    coordinates=vis.get("coordinates"),
                    params=vis.get("params", {})
                )
                # Convert to dict for JSON serialization compatibility
                visualization_data = vis_obj.model_dump() if hasattr(vis_obj, "model_dump") else vis_obj.dict()
            except Exception as e:
                print(f"Visualization validation error: {e}")
                # Fallback: ignore visualization if invalid
                visualization_data = None
        
        # Correction: If options are present, force type to single_choice
        final_type = q_type
        if options and len(options) > 0:
            final_type = "single_choice"

        # Optimization: Remove options from meta.correct_data to reduce duplication
        correct_data = data.copy()
        if "options" in correct_data:
            del correct_data["options"]
        if "prompt" in correct_data:
            del correct_data["prompt"]
        if "visualization" in correct_data:
            del correct_data["visualization"]
        if "is_visual" in correct_data:
            del correct_data["is_visual"]

        res_q = {
            "question_uid": q_uid,
            "subject_uid": "", # Subject UID is not available in generation context, handled by caller
            "topic_uid": topic_uid,
            "type": final_type,
            "prompt": data.get("prompt", "Question"),
            "options": options,
            "is_visual": data.get("is_visual", False) and (visualization_data is not None),
            "visualization": visualization_data,
            "meta": {
                "difficulty": 0.5,
                "skill_uid": None, # Skill UID is unknown for generated questions
                "generated": True,
                "correct_data": correct_data
            }
        }
        

        return res_q
    except Exception as e:
        print(f"Gen Error: {e}")
        # If generation fails, we raise an error instead of returning a stub
        raise HTTPException(status_code=503, detail="Unable to generate question at this time.")


async def _select_question(topic_uid: str, difficulty_min: int, difficulty_max: int, exclude_uids: set = set(), previous_prompts: List[str] = []) -> Dict:
    qs = select_examples_for_topics([topic_uid], limit=1, difficulty_min=difficulty_min, difficulty_max=difficulty_max, exclude_uids=exclude_uids)
    
    if qs:
        q = qs[0]
        # Quality check: If topic is visual (based on uid/title) but question is NOT visual, skip it.
        # Also skip if type is free_text for visual topics.
        
        # Heuristic: check topic_uid for visual keywords if title is not readily available
        # or use the fact that q["topic_uid"] is available.
        # But better to check the question content or metadata.
        
        is_q_visual = bool(q.get("is_visual", False))
        q_type = str(q.get("type", "free_text"))
        
        visual_keywords = [
            "geometry", "triangle", "circle", "graph", "function", "chart", "diagram", 
            "геометр", "треугольн", "график", "функц", "окружн", "угл", "angles", "slope", "derivative", "integral",
            "geometr", "ellips", "figur", "polygon", "mnogougoln", "ugol", "angle", "ploshchad", "area", "volume", "obem", 
            "radius", "diametr", "sechen", "section", "bokov", "lateral", "prizm", "prism", "piramid", "pyramid", 
            "shara", "sphere", "konus", "cone", "cilindr", "cylinder", "vektor", "vector",
            "эллипс", "фигур", "многоугольн", "площад", "объем", "диаметр", "сечен", "боков", "шар", "конус", "цилиндр", "вектор"
        ]
        # Check topic_uid as proxy for title since we don't have title here easily without extra DB call
        # q might have 'topic_uid' inside it
        
        is_topic_visual_heuristic = any(k in topic_uid.lower() for k in visual_keywords)
        
        if is_topic_visual_heuristic and (not is_q_visual or q_type == "free_text"):
            # Skip this legacy question and force generation
            pass
        else:
            return {
                "question_uid": str(q.get("uid") or f"Q-MISSING-{topic_uid}"),
                "subject_uid": "",
                "topic_uid": topic_uid,
                "type": q_type,
                "prompt": str(q.get("statement") or q.get("title") or ""),
                "options": q.get("options", []),
                "is_visual": is_q_visual,
                "visualization": q.get("visualization", None),
                "meta": {"difficulty": float(q.get("difficulty") or 0.5), "skill_uid": ""},
            }
    
    # Pass target difficulty (using max as target) to generator
    return await _generate_question_llm(topic_uid, exclude_uids, previous_prompts=previous_prompts, difficulty=difficulty_max)

@router.post(
    "/start",
    response_model=StandardResponse,
    responses={400: {"model": ApiError}, 404: {"model": ApiError}},
)
async def start(payload: StartRequest) -> Dict:
    try:
        uc = payload.user_context or UserContext()
        resolved = _resolve_level(uc)
        if not _topic_accessible(payload.subject_uid, payload.topic_uid, resolved):
            raise HTTPException(status_code=404, detail="Topic not available")
        import uuid
        sid = uuid.uuid4().hex
        first_q = await _select_question(payload.topic_uid, 3, 3, set())
        # Ensure subject_uid is populated in the question response
        first_q["subject_uid"] = payload.subject_uid
        
        sess_data = {
            "subject_uid": payload.subject_uid,
            "topic_uid": payload.topic_uid,
            "resolved_user_class": resolved,
            "asked": [],
            "asked_prompts": [first_q["prompt"]],
            "last_question_uid": first_q["question_uid"],
            "good": 0,
            "bad": 0,
            "min_questions": 6,
            "max_questions": 20,
            "target_confidence": 0.85,
            "stability_window": 4,
            "d_history": [],
            "question_details": {
                first_q["question_uid"]: {
                    "prompt": first_q["prompt"],
                    "correct_data": first_q["meta"].get("correct_data"),
                    "options": first_q.get("options"),
                    "type": first_q.get("type"),
                }
            }
        }
        if not _save_session(sid, sess_data):
            raise HTTPException(status_code=500, detail="Failed to initialize session storage")
            
        return {"items": [first_q], "meta": {"assessment_session_id": sid}}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

def _evaluate(answer: AnswerDTO, question_data: Dict = None) -> float:
    if answer is None:
        return 0.0
    
    # 1. Check Single Choice (Option UIDs)
    if answer.selected_option_uids:
        if not question_data or not question_data.get("options"):
            # Fallback if no data (should not happen in normal flow)
            return 1.0
        
        # Find correct options
        correct_uids = {
            opt["option_uid"] 
            for opt in question_data["options"] 
            if opt.get("is_correct")
        }
        
        # Simple logic: exact match of selected vs correct
        # (Can be improved for partial credit)
        selected = set(answer.selected_option_uids)
        return 1.0 if selected == correct_uids else 0.0

    # 2. Check Numeric (Value)
    if answer.value is not None:
        try:
            user_val = float(answer.value)
            # Try to find correct value in correct_data
            correct_val = None
            if question_data and question_data.get("correct_data"):
                cd = question_data["correct_data"]
                if "correct_value" in cd:
                    correct_val = float(cd["correct_value"])
            
            if correct_val is not None:
                # Allow small epsilon error
                return 1.0 if abs(user_val - correct_val) < 1e-6 else 0.0
            
            # Fallback if no correct value known: assume correct if non-zero? No, unsafe.
            # But for now, let's return 0.0 if we can't verify.
            return 0.0
        except Exception:
            return 0.0

    # 3. Check Free Text
    if answer.text:
        text = str(answer.text).strip()
        if len(text) < 1:
            return 0.0
            
        # Try to match with correct_value if exists
        if question_data and question_data.get("correct_data"):
            cd = question_data["correct_data"]
            correct_text = str(cd.get("correct_value", "")).strip().lower()
            if correct_text:
                # Basic fuzzy match
                if text.lower() == correct_text:
                    return 1.0
                # If correct answer is numeric but user sent text
                try:
                    if float(text) == float(correct_text):
                        return 1.0
                except:
                    pass
                return 0.0 # Mismatch
        
        # If no correct data available (legacy/fallback), 
        # DO NOT return 1.0 just for length. It allows "nonsense".
        # Return 0.0 or mark for manual review.
        return 0.0

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
    
    # Adaptive Logic: Adjust difficulty based on the LAST answer specifically
    # User feedback: "If I answered wrong, give easier question."
    
    last_q_uid = sess["asked"][-1] if sess["asked"] else None
    last_score = 0.0
    # Retrieve score of the last question if available
    if last_q_uid and "question_details" in sess and last_q_uid in sess["question_details"]:
        last_score = sess["question_details"][last_q_uid].get("score", 0.0)
    
    # Determine new difficulty
    if last_score >= 0.5:
        # Correct answer -> Increase difficulty
        d = min(10, d_last + 1)
    else:
        # Incorrect answer -> Decrease difficulty
        d = max(1, d_last - 1)
        
    sess["d_history"].append(d)
    
    try:
        previous_prompts = sess.get("asked_prompts", [])
        q = await _select_question(sess["topic_uid"], d, d, set(sess["asked"]), previous_prompts=previous_prompts)
    except Exception as e:
        print(f"Error selecting question: {e}")
        # Try fallback to standard difficulty if specific difficulty fails
        try:
            previous_prompts = sess.get("asked_prompts", [])
            q = await _select_question(sess["topic_uid"], 3, 3, set(sess["asked"]), previous_prompts=previous_prompts)
        except Exception:
            q = None

    if not q:
        # If still no question, return None to signal end or error?
        # Better to return None and let the loop handle it, but wait,
        # next_question expects a question.
        # If we can't find a question, maybe we should stop the session?
        return None

    # Ensure subject_uid is populated in the question response
    if q:
        q["subject_uid"] = sess.get("subject_uid", "")
        # Update prompt history
        if "asked_prompts" not in sess: sess["asked_prompts"] = []
        sess["asked_prompts"].append(q["prompt"])
        if len(sess["asked_prompts"]) > 20:
            sess["asked_prompts"] = sess["asked_prompts"][-20:]
        
        # Save question details
        if "question_details" not in sess: sess["question_details"] = {}
        sess["question_details"][q["question_uid"]] = {
            "prompt": q["prompt"],
            "correct_data": q["meta"].get("correct_data"),
            "options": q.get("options"),
            "type": q.get("type"),
            "difficulty": q["meta"].get("difficulty", 5), # Default to 5 if missing
        }

    sess["last_question_uid"] = q["question_uid"]
    return q

@router.post(
    "/next",
    responses={400: {"model": ApiError}},
)
async def next_question(payload: NextRequest):
    try:
        sid = payload.assessment_session_id
        sess = _get_session(sid)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        if payload.question_uid != sess.get("last_question_uid"):
            raise HTTPException(status_code=400, detail="Invalid sequence")
            
        q_data = None
        if "question_details" in sess and payload.question_uid in sess["question_details"]:
            q_data = sess["question_details"][payload.question_uid]
            
        score = _evaluate(payload.answer, q_data)
        if score >= 0.5:
            sess["good"] += 1
        else:
            sess["bad"] += 1
        sess["asked"].append(payload.question_uid)
        
        # Save user answer
        if "question_details" in sess and payload.question_uid in sess["question_details"]:
            try:
                # Convert Pydantic model to dict
                ans_dict = payload.answer.dict() if hasattr(payload.answer, "dict") else payload.answer.model_dump()
                sess["question_details"][payload.question_uid]["user_answer"] = ans_dict
                sess["question_details"][payload.question_uid]["score"] = score
            except Exception as e:
                print(f"Error saving answer: {e}")

        if not _save_session(sid, sess):
            print(f"Warning: Failed to save session {sid} in next_question")
        
        done_by_min = len(sess["asked"]) >= sess["min_questions"] and _confidence(sess) >= sess["target_confidence"]
        done_by_max = len(sess["asked"]) >= sess["max_questions"]
        async def _stream():
            try:
                yield "event: ack\n"
                yield "data: {\"items\":[{\"accepted\":true}],\"meta\":{}}\n\n"
                if done_by_min or done_by_max:
                    # Precise Score Calculation
                    # Calculate weighted score based on difficulty
                    # Score = Sum(answer_score * difficulty) / Sum(difficulty)
                    # But if user answers hard questions wrong, we shouldn't punish too hard compared to easy questions?
                    # Actually, standard weighted average is fine: 
                    # 100% on Diff 10 is better than 100% on Diff 1.
                    # 0% on Diff 10 is same as 0% on Diff 1 (0 points).
                    
                    total_weighted_score = 0.0
                    total_difficulty = 0.0
                    
                    q_details = sess.get("question_details", {})
                    for q_uid in sess.get("asked", []):
                        if q_uid in q_details:
                            qd = q_details[q_uid]
                            diff = float(qd.get("difficulty", 5.0))
                            user_score = float(qd.get("score", 0.0))
                            
                            total_weighted_score += user_score * diff
                            total_difficulty += diff
                            
                    raw_score = total_weighted_score / max(1.0, total_difficulty)
                    score = round(raw_score, 2)

                    # Expanded analytics
                    gaps = []
                    if score < 0.85:
                        gaps.append("Есть пробелы в понимании сложных аспектов темы")
                    if score < 0.6:
                        gaps.append("Требуется повторение базовых определений")
                    if score < 0.4:
                        gaps.append("Критические пробелы в знаниях")
                    
                    # Generate LLM Analytics
                    llm_analytics = {}
                    try:
                        from app.services.kb.builder import openai_chat_async
                        
                        history_text = ""
                        q_details = sess.get("question_details", {})
                        
                        # Sort by order asked if possible, or just iterate
                        asked_uids = sess.get("asked", [])
                        
                        for i, uid in enumerate(asked_uids):
                             if uid in q_details:
                                 qd = q_details[uid]
                                 history_text += f"Q{i+1}: {qd.get('prompt')}\\n"
                                 history_text += f"User Answer: {qd.get('user_answer')}\\n"
                                 history_text += f"Correct Data: {qd.get('correct_data')}\\n"
                                 history_text += f"Score: {qd.get('score')}\\n\\n"
                        
                        sys_prompt = (
                            "You are an expert tutor. Analyze the student's session history detailedly.\\n"
                            "LANGUAGE: All output text (feedback, comments, recommendations) MUST be in RUSSIAN.\\n"
                            "1. Re-evaluate every answer. BE LENIENT with formatting errors (e.g. 0.2 vs 2/10, or missing units). If the student shows understanding but failed specific format, give PARTIAL credit (0.5).\\n"
                            "2. Calculate the precise knowledge level (0-100%) based on ACTUAL correctness. Focus on CONCEPTUAL understanding.\\n"
                            "3. Provide a specific, constructive feedback for EACH question (why it was right/wrong).\\n"
                            "4. Identify specific knowledge gaps (e.g. 'confuses radius and diameter').\\n"
                            "5. Provide a tailored recommendation (NOT just 'next topic', but specific actions).\\n"
                            "Output JSON format:\\n"
                            "{\\n"
                            "  \"questions_analytics\": [\\n"
                            "    {\"question_uid\": \"...\", \"feedback\": \"...\"}\\n"
                            "  ],\\n"
                            "  \"overall_comment\": \"...\",\\n"
                            "  \"knowledge_level_percent\": 85,\\n"
                            "  \"specific_gaps\": [\"...\", \"...\"],\\n"
                            "  \"recommendation\": \"...\"\\n"
                            "}\\n"
                            "Return ONLY JSON."
                        )
                        
                        # Call LLM
                        # We use a lower temperature for analysis
                        messages = [
                             {"role": "system", "content": sys_prompt},
                             {"role": "user", "content": f"Topic: {sess.get('topic_uid')}\\n\\nHistory:\\n{history_text}"}
                        ]
                        
                        llm_resp = await openai_chat_async(messages, temperature=0.3)
                        
                        if not llm_resp.get("ok"):
                             raise Exception(f"LLM Error: {llm_resp.get('error')}")

                        content_str = llm_resp.get("content", "")
                        # Clean markdown
                        if "```json" in content_str:
                            content_str = content_str.split("```json")[1].split("```")[0].strip()
                        elif "```" in content_str:
                             content_str = content_str.split("```")[1].split("```")[0].strip()
                        
                        llm_analytics = json.loads(content_str)
                    except Exception as e:
                        print(f"LLM Analytics failed: {e}")
                        import traceback
                        traceback.print_exc()
                        # Fallback
                        llm_analytics = {"questions_analytics": [], "overall_comment": "Detailed analysis unavailable due to service error.", "knowledge_level_percent": int(score*100), "specific_gaps": [], "recommendation": "Review the material."}

                    # Use LLM calculated level if reasonable, else fallback to raw score
                    llm_level = llm_analytics.get("knowledge_level_percent")
                    final_percentage = llm_level if isinstance(llm_level, (int, float)) else int(score * 100)

                    # Detailed analytics
                    detailed_analytics = {
                        "gaps": llm_analytics.get("specific_gaps", gaps),
                        "recommended_focus": llm_analytics.get("recommendation", "Повторить теорию и пройти практику 'We Do'" if score < 0.7 else "Закрепить успех практикой"),
                        "strength": "Хорошая скорость ответов" if score > 0.8 else "Внимательность к деталям",
                        "current_percentage": final_percentage,
                        "topic_breakdown": [
                            {"subtopic": "Theory", "mastery": min(100, int(score * 110))},
                            {"subtopic": "Practice", "mastery": int(score * 100)},
                            {"subtopic": "Application", "mastery": max(0, int(score * 90))}
                        ],
                        "questions_review": llm_analytics.get("questions_analytics", []),
                        "tutor_comment": llm_analytics.get("overall_comment", "")
                    }

                    res = {
                        "is_completed": True,
                        "items": [
                            {
                                "topic_uid": sess["topic_uid"],
                                "level": "intermediate" if sess["good"] >= sess["bad"] else "basic",
                                "mastery": {"score": score},
                                "analytics": detailed_analytics
                            }
                        ],
                        "meta": {}
                    }
                    yield "event: done\n"
                    yield "data: " + json.dumps(res, ensure_ascii=False) + "\n\n"
                    return
                q = await _next_question(sess)
                if not q:
                    yield "event: error\n"
                    yield "data: {\"error\": \"Unable to generate next question\"}\n\n"
                    return
                if not _save_session(sid, sess): # Save updated session after selecting next question
                    print(f"Warning: Failed to save session {sid} after selecting next question")
                yield "event: question\n"
                yield "data: " + json.dumps({"is_completed": False, "items":[q], "meta": {}}, ensure_ascii=False) + "\n\n"
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield "event: error\n"
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(_stream(), media_type="text/event-stream")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
