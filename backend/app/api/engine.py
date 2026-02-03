
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import json
import re
from app.services.graph.neo4j_repo import relation_context, neighbors, get_node_details, get_driver, Neo4jRepo
from app.config.settings import settings
from app.services.roadmap_planner import plan_route
from app.services.questions import select_examples_for_topics, all_topic_uids_from_examples
from app.api.common import ApiError, StandardResponse
from app.core.context import get_tenant_id
from app.schemas.roadmap import RoadmapRequest
from app.schemas.context import UserContext
from app.services.reasoning.gaps import compute_gaps
from app.services.reasoning.next_best_topic import next_best_topics
from app.services.reasoning.mastery_update import update_mastery
from app.services.curriculum.repo import get_graph_view
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from starlette.responses import StreamingResponse
from app.services.graph.neo4j_repo import Neo4jRepo
from app.services.questions import select_examples_for_topics
from app.events.publisher import get_redis
from app.services.kb.builder import openai_chat_async
from app.services.visualization.geometry import GeometryEngine
import random
import uuid

router = APIRouter()

# --- Graph / Viewport ---

class NodeDTO(BaseModel):
    id: int
    uid: Optional[str] = None
    label: Optional[str] = None
    labels: List[str] = []

class EdgeDTO(BaseModel):
    from_: int = Field(..., alias="from")
    to: int
    type: str

class ViewportResponse(BaseModel):
    nodes: List[NodeDTO]
    edges: List[EdgeDTO]
    center_uid: str
    depth: int

@router.get("/node/{uid}", response_model=StandardResponse)
async def get_node(uid: str) -> Dict:
    data = get_node_details(uid, tenant_id=get_tenant_id())
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"items": [data], "meta": {}}

@router.get("/viewport", response_model=StandardResponse)
async def viewport(center_uid: str, depth: int = 1) -> Dict:
    ns, es = neighbors(center_uid, depth=depth, tenant_id=get_tenant_id())
    return {"items": ns, "meta": {"edges": es, "center_uid": center_uid, "depth": depth}}

class PathfindInput(BaseModel):
    target_uid: str

class PathfindResponse(BaseModel):
    target: str
    path: List[str]

@router.post("/pathfind", summary="Find learning path", response_model=PathfindResponse)
async def pathfind(payload: PathfindInput) -> Dict:
    drv = get_driver()
    with drv.session() as s:
        res = s.run(
            "MATCH (t:Topic {uid:$uid})-[:PREREQ*0..]->(p:Topic) RETURN collect(DISTINCT p.uid) AS uids",
            {"uid": payload.target_uid}
        ).single()
        closure: List[str] = res["uids"] if res else []
        edges = s.run(
            "MATCH (a:Topic)-[:PREREQ]->(b:Topic) WHERE a.uid IN $uids AND b.uid IN $uids "
            "RETURN a.uid AS a, b.uid AS b",
            {"uids": closure}
        )
        g: Dict[str, List[str]] = {u: [] for u in closure}
        indeg: Dict[str, int] = {u: 0 for u in closure}
        for r in edges:
            g[r["b"]].append(r["a"])
            indeg[r["a"]] += 1
    drv.close()
    q: List[str] = [u for u, d in indeg.items() if d == 0]
    ordered: List[str] = []
    seen: Set[str] = set()
    while q:
        u = q.pop(0)
        if u in seen:
            continue
        seen.add(u)
        ordered.append(u)
        for v in g.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return {"target": payload.target_uid, "path": ordered}

# --- Chat ---

class ChatInput(BaseModel):
    question: str = Field(..., description="User question about the relationship.")
    from_uid: str = Field(..., description="Source node UID.")
    to_uid: str = Field(..., description="Target node UID.")

class ChatResponse(BaseModel):
    answer: str
    usage: Optional[Dict] = None
    context: Dict = {}

@router.post("/chat", summary="Explain relationship (RAG)", response_model=ChatResponse)
async def chat(payload: ChatInput) -> Dict:
    try:
        from openai import AsyncOpenAI
        from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
    except Exception:
        raise HTTPException(status_code=503, detail="OpenAI client is not available")

    ctx = relation_context(payload.from_uid, payload.to_uid, tenant_id=get_tenant_id())
    oai = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    messages = [
        {"role": "system", "content": "You are a graph expert. Explain why the relationship exists using provided metadata."},
        {"role": "user", "content": f"Q: {payload.question}\nFrom: {ctx.get('from_title','')} ({payload.from_uid})\nTo: {ctx.get('to_title','')} ({payload.to_uid})\nRelation: {ctx.get('rel','')}\nProps: {ctx.get('props',{})}"},
    ]

    try:
        resp = await oai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    except Exception:
        raise HTTPException(status_code=502, detail="OpenAI request failed")

    usage = resp.usage or None
    answer = resp.choices[0].message.content if resp.choices else ""
    return {"answer": answer, "usage": (usage.model_dump() if hasattr(usage, 'model_dump') else None), "context": ctx}

# --- Roadmap ---

class RoadmapNode(BaseModel):
    topic_uid: str
    title: str
    description: Optional[str] = None
    status: str = "locked"  # locked, available, completed
    progress_percentage: float = 0.0

class RoadmapResponse(BaseModel):
    nodes: List[RoadmapNode]

@router.post("/roadmap", summary="Build adaptive roadmap", response_model=RoadmapResponse)
async def roadmap(payload: RoadmapRequest) -> Dict:
    # Custom logic to support the "5 nodes + I/We/You Do" requirement
    subject_uid = payload.subject_uid
    progress = payload.current_progress or {}
    
    # 1. Fetch Candidate Topics (limit 20 to give LLM choices)
    topics = []
    rows = []
    focus_uid = payload.focus_topic_uid
    
    if settings.neo4j_uri:
        repo = Neo4jRepo()
        
        if focus_uid:
            # Query prioritizing the focus topic and its neighbors (by PREREQ distance)
            # Also determine relationship type: 'self', 'prerequisite' (t -> f), 'dependent' (f -> t)
            query = """
            MATCH (sub:Subject {uid: $su})
            MATCH (sub)-[:CONTAINS*]->(t:Topic)
            
            OPTIONAL MATCH path = shortestPath((t)-[:PREREQ*..3]-(f:Topic {uid: $focus}))
            WHERE t <> f
            WITH t, path
            
            WITH t, path,
                 CASE 
                   WHEN t.uid = $focus THEN 'self'
                   WHEN path IS NOT NULL AND nodes(path)[0] = t THEN 'prerequisite'
                   WHEN path IS NOT NULL AND nodes(path)[-1] = t THEN 'dependent'
                   ELSE 'related'
                 END AS rel_type,
                 length(path) as dist
            
            OPTIONAL MATCH (t)-[:PREREQ]->(p:Topic)
            OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(s:Skill)
            WITH t, rel_type, dist, collect(DISTINCT p.uid) as prereqs, collect(DISTINCT s.title) as skills
            
            RETURN t.uid AS uid, t.title AS title, t.description AS description, prereqs, skills, rel_type, dist
            ORDER BY (CASE WHEN dist IS NULL THEN 100 ELSE dist END) ASC, t.title ASC
            LIMIT 50
            """
            print(f"Running roadmap query for {subject_uid} with focus {focus_uid}")
            rows = repo.read(query, {"su": subject_uid, "focus": focus_uid})
        else:
            # Standard query (Alphabetical / Graph order)
            query = """
            MATCH (sub:Subject {uid: $su})
            MATCH (sub)-[:CONTAINS*]->(t:Topic)
            OPTIONAL MATCH (t)-[:PREREQ]->(p:Topic)
            OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(s:Skill)
            WITH t, collect(DISTINCT p.uid) as prereqs, collect(DISTINCT s.title) as skills
            RETURN t.uid AS uid, t.title AS title, t.description AS description, prereqs, skills
            ORDER BY t.title ASC
            LIMIT 50
            """
            print(f"Running roadmap query for {subject_uid}")
            rows = repo.read(query, {"su": subject_uid})
            
        print(f"Found {len(rows)} rows")
        repo.close()

    # 2. LLM Personalization & Description Generation
    # We want to select top 8 topics based on gaps (low scores) and generate descriptions if missing.
    selected_rows = []
    
    # Map rows by UID for easy access
    rows_map = {r["uid"]: r for r in rows}
    
    # Identify focus topic title for LLM context
    focus_title = ""
    if focus_uid and focus_uid in rows_map:
        focus_title = rows_map[focus_uid]["title"]
    
    # Prepare candidates for LLM
    candidates_info = []
    for r in rows:
        uid = r["uid"]
        score = progress.get(uid, 0.0)
        candidates_info.append({
            "uid": uid,
            "title": r["title"],
            "description": r.get("description") or "",
            "current_score": score,
            "relationship": r.get("rel_type", "unknown"),
            "distance": r.get("dist", 100),
            "prerequisites": r.get("prereqs", []),
            "skills": r.get("skills", [])
        })

    used_llm = False
    if settings.openai_api_key and candidates_info:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
            
            prompt = (
                "You are an adaptive learning AI. Select the best 5-8 topics for a student roadmap from the list below.\n"
                f"The student is currently focusing on topic: '{focus_title}' (UID: {focus_uid}).\n"
                "Rules for Roadmap Construction:\n"
                "1. **GOAL**: The roadmap MUST help the student master the focus topic.\n"
                "2. **REMEDIATION (Score < 0.6)**: If the focus topic score is low, include immediate prerequisites (distance=1) AND the focus topic itself (as the target).\n"
                "3. **FOCUS LOOP (Score 0.6 - 0.85)**: Prioritize the focus topic and closely related topics (shared skills/methods).\n"
                "4. **PROGRESSION (Score > 0.85)**: If mastered, suggest dependent topics.\n"
                "5. **Skills**: Use 'skills' field to find relevant topics even if 'distance' is high (e.g. topics sharing 'Graph Analysis').\n"
                "6. GENERATE a short, engaging description (in Russian) for any topic that has an empty description.\n"
                "Return a valid JSON object with a key 'selected_topics' containing a list of objects: {'uid': '...', 'description': '...'}.\n"
                "The list must be ordered by priority (highest priority first).\n\n"
                f"Candidates: {json.dumps(candidates_info, ensure_ascii=False)}"
            )
            
            completion = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful tutor assistant. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            content = completion.choices[0].message.content
            if content:
                data = json.loads(content)
                selected_items = data.get("selected_topics", [])
                
                # Reconstruct selected_rows based on LLM order
                for item in selected_items:
                    uid = item.get("uid")
                    if uid in rows_map:
                        r = rows_map[uid]
                        # Update description if LLM provided one
                        new_desc = item.get("description")
                        if new_desc and (not r.get("description") or len(r["description"]) < 5):
                            r["description"] = new_desc
                        selected_rows.append(r)
                
                used_llm = True
                print(f"LLM selected {len(selected_rows)} topics")
                
        except Exception as e:
            print(f"LLM Personalization failed, falling back to default order. Error: {e}")

    # Fallback if LLM failed or returned nothing
    if not selected_rows:
        # Fallback Strategy:
        # 1. Always include focus topic (dist=0)
        # 2. Then closest neighbors (dist=1)
        # 3. Then others
        
        # Sort rows by distance (dist=0 first)
        def sort_key(r):
            d = r.get("dist")
            if d is None: return 100
            return d
            
        sorted_rows = sorted(rows, key=sort_key)
        selected_rows = sorted_rows[:8]
    else:
        # Ensure we have at most 8
        selected_rows = selected_rows[:8]
        
    # 3. Process selected rows to build RoadmapNodes
    count = 0
    for r in selected_rows:
        if count >= 8:
            break
        
        t_uid = r["uid"]
            
        # Determine status based on progress
        p_val = progress.get(t_uid, 0.0)
        if p_val >= 0.85:
            status = "completed"
        elif p_val > 0:
            status = "available"
        else:
            status = "locked" # Simple logic
        
        # If it's the first one and locked, make it available
        if count == 0 and status == "locked":
            status = "available"
            
        progress_percentage = p_val * 100.0

        topics.append(RoadmapNode(
            topic_uid=t_uid,
            title=r["title"],
            description=r.get("description"),
            status=status,
            progress_percentage=progress_percentage
        ))
        count += 1

    return {"nodes": topics}

# --- Knowledge / Topics ---

class GoalType(str, Enum):
    exam = "exam"
    improve_grade = "improve_grade"
    study_topics = "study_topics"
    homework = "homework"

class ExamType(str, Enum):
    oge = "ОГЭ"
    ege_profile = "ЕГЭ Профиль"
    ege_base = "ЕГЭ БАЗА"

class TopicsAvailableRequest(BaseModel):
    subject_uid: Optional[str] = None
    subject_title: Optional[str] = None
    user_context: UserContext
    curriculum_code: Optional[str] = None
    goal_type: Optional[GoalType] = None
    exam_type: Optional[ExamType] = None

    @field_validator('exam_type', mode='before')
    @classmethod
    def empty_string_to_none(cls, v: Any) -> Any:
        if v == "":
            return None
        return v

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

def _filter_rows(rows: List[Dict], allowed_topics: Optional[Set[str]], payload: TopicsAvailableRequest, resolved: int) -> List[Dict]:
    results = []
    for r in rows or []:
        mn = r.get("user_class_min")
        mx = r.get("user_class_max")
        
        include = True
        
        # Curriculum Whitelist Check
        if allowed_topics is not None and r.get("topic_uid") not in allowed_topics:
            include = False
        
        if include:
            # Goal / Class Filtering
            
            try:
                mn_val = int(mn) if mn is not None else None
                mx_val = int(mx) if mx is not None else None
                
                is_exam = payload.goal_type == GoalType.exam
                
                if is_exam:
                    # Memory 01KG0022Y97B03DEJ3W11AA854: 
                    # Filters topics by curriculum grade limits for exams (OGE<=9, EGE<=11).
                    exam_limit = 11 # Default to 11
                    if payload.exam_type == ExamType.oge:
                        exam_limit = 9
                    
                    # Filter 1: Exclude topics that start AFTER the exam limit
                    if mn_val is not None and mn_val > exam_limit:
                        include = False
                    
                    # Filter 2: Exclude topics that start AFTER the user's current class
                    # (Prevent 3rd grader from seeing 7th grade topics, even if for OGE)
                    # Skip this check if resolved class is 0 (undefined/admin)
                    if mn_val is not None and resolved > 0 and resolved < mn_val:
                        include = False
                        
                    # Note: We intentionally ALLOW topics where resolved > mx_val (Reviewing past material)
                    
                else:
                    # Default logic (study_topics, homework, improve_grade)
                    # Filters topics by user class
                    if mn_val is not None and resolved > 0 and resolved < mn_val:
                        include = False
                    if mx_val is not None and resolved > 0 and resolved > mx_val:
                        include = False
                        
            except (ValueError, TypeError):
                pass
        
        if include:
            results.append({
                "topic_uid": r.get("topic_uid"),
                "title": r.get("title"),
                "user_class_min": int(mn) if isinstance(mn, (int, float)) else None,
                "user_class_max": int(mx) if isinstance(mx, (int, float)) else None,
                "difficulty_band": r.get("difficulty_band") or "standard",
                "prereq_topic_uids": [p for p in (r.get("prereq_topic_uids") or []) if p],
            })
    return results

@router.post("/topics/available", response_model=StandardResponse)
async def topics_available(payload: TopicsAvailableRequest) -> Dict:
    # Extract level/class from context attributes if present, else fallback
    # Assuming attributes might have 'grade' or 'class'
    ctx = payload.user_context
    user_class = ctx.user_class
    if user_class is None:
        user_class = ctx.attributes.get("user_class") or ctx.attributes.get("grade")
    
    age = ctx.age
    if age is None:
        age = ctx.attributes.get("age")
    
    resolved = int(user_class) if user_class is not None else _age_to_class(age)
    
    # Curriculum Filter Preparation
    allowed_topics: Optional[Set[str]] = None
    if payload.curriculum_code:
        cv = get_graph_view(payload.curriculum_code)
        if cv.get("ok") and cv.get("nodes"):
             root_nodes = [n["canonical_uid"] for n in cv["nodes"]]
             if root_nodes:
                 repo_cv = Neo4jRepo()
                 try:
                     res_cv = repo_cv.read(
                        "UNWIND $roots AS root MATCH (t:Topic {uid:root})-[:PREREQ*0..]->(p:Topic) RETURN collect(DISTINCT p.uid) AS uids",
                        {"roots": root_nodes}
                     )
                     if res_cv and res_cv[0].get("uids"):
                         allowed_topics = set(res_cv[0]["uids"])
                     else:
                         allowed_topics = set()
                 except Exception:
                     allowed_topics = set()
                 finally:
                     repo_cv.close()
        
        if allowed_topics is None:
             # Curriculum code provided but invalid or not found -> block all
             allowed_topics = set()

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
                    "WITH t, collect(pre.uid) AS pre1 "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       pre1 AS prereq_topic_uids "
                    "UNION "
                    "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t:Topic) "
                    "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                    "WITH t, collect(pre.uid) AS pre2 "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       pre2 AS prereq_topic_uids"
                ),
                {"su": su},
            )
            if not rows and (payload.subject_title or "").strip():
                rows = repo.read(
                    (
                        "MATCH (sub:Subject) WHERE toUpper(sub.title)=toUpper($t) "
                        "MATCH (sub)-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
                        "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                        "WITH t, collect(pre.uid) AS pre1 "
                        "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                        "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                        "       pre1 AS prereq_topic_uids "
                        "UNION "
                        "MATCH (sub:Subject) WHERE toUpper(sub.title)=toUpper($t) "
                        "MATCH (sub)-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t:Topic) "
                        "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                        "WITH t, collect(pre.uid) AS pre2 "
                        "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                        "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                        "       pre2 AS prereq_topic_uids"
                    ),
                    {"t": payload.subject_title},
                )
            topics.extend(_filter_rows(rows, allowed_topics, payload, resolved))
            repo.close()
        except Exception:
            topics = []
    if not topics and su:
        try:
            repo = Neo4jRepo()
            rows = repo.read(
                (
                    "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
                    "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       collect(pre.uid) AS prereq_topic_uids "
                    "UNION "
                    "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t:Topic) "
                    "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       collect(pre.uid) AS prereq_topic_uids"
                ),
                {"su": su},
            )
            topics.extend(_filter_rows(rows, allowed_topics, payload, resolved))
            repo.close()
        except Exception:
            ...
    if not topics and (payload.subject_title or "").strip():
        try:
            repo = Neo4jRepo()
            rows = repo.read(
                (
                    "MATCH (sub:Subject) WHERE toUpper(sub.title)=toUpper($t) "
                    "MATCH (sub)-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
                    "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       collect(pre.uid) AS prereq_topic_uids "
                    "UNION "
                    "MATCH (sub:Subject) WHERE toUpper(sub.title)=toUpper($t) "
                    "MATCH (sub)-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t:Topic) "
                    "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                    "RETURN t.uid AS topic_uid, t.title AS title, t.user_class_min AS user_class_min, "
                    "       t.user_class_max AS user_class_max, t.difficulty_band AS difficulty_band, "
                    "       collect(pre.uid) AS prereq_topic_uids"
                ),
                {"t": payload.subject_title},
            )
            topics.extend(_filter_rows(rows, allowed_topics, payload, resolved))
            repo.close()
        except Exception:
            ...
    if not topics and not (payload.subject_uid or payload.subject_title or payload.goal_type):
        # Fallback to all examples only if no specific context was requested
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

# --- Adaptive Questions ---

class AdaptiveQuestionsInput(BaseModel):
    subject_uid: Optional[str] = None
    progress: Dict[str, float]
    count: int = 10
    difficulty_min: int = 1
    difficulty_max: int = 5
    exclude: List[str] = []

@router.post("/adaptive_questions", summary="Get adaptive questions", response_model=StandardResponse)
async def adaptive_questions(payload: AdaptiveQuestionsInput) -> Dict:
    tid = get_tenant_id()
    roadmap_items = plan_route(payload.subject_uid, payload.progress, limit=payload.count * 3, tenant_id=tid)
    topic_uids = [it["uid"] for it in roadmap_items] or all_topic_uids_from_examples()
    examples = select_examples_for_topics(
        topic_uids=topic_uids,
        limit=payload.count,
        difficulty_min=payload.difficulty_min,
        difficulty_max=payload.difficulty_max,
        exclude_uids=set(payload.exclude),
        tenant_id=tid,
    )
    return {"items": examples, "meta": {}}

# --- Reasoning / Gaps ---

class GapsRequest(BaseModel):
    subject_uid: str
    progress: Dict[str, float] = Field(default_factory=dict)
    goals: Optional[List[str]] = None
    prereq_threshold: float = 0.7

@router.post("/gaps", response_model=StandardResponse)
async def gaps(req: GapsRequest):
    res = compute_gaps(req.subject_uid, req.progress, req.goals, req.prereq_threshold)
    return {"items": [], "meta": res}

class NextBestRequest(BaseModel):
    subject_uid: str
    progress: Dict[str, float] = Field(default_factory=dict)
    prereq_threshold: float = 0.7
    top_k: int = 5
    alpha: float = 0.5
    beta: float = 0.3

@router.post("/next-best-topic", response_model=StandardResponse)
async def next_best_topic(req: NextBestRequest):
    res = next_best_topics(req.subject_uid, req.progress, req.prereq_threshold, req.top_k, req.alpha, req.beta)
    return {"items": res["items"], "meta": {}}

class MasteryUpdateRequest(BaseModel):
    entity_uid: str
    kind: str = Field(pattern="^(Topic|Skill)$")
    score: float
    prior_mastery: float
    confidence: Optional[float] = None

@router.post("/mastery/update", response_model=StandardResponse)
async def mastery_update(req: MasteryUpdateRequest):
    res = update_mastery(req.prior_mastery, req.score, req.confidence)
    return {"items": [{"uid": req.entity_uid, "kind": req.kind, **res}], "meta": {}}


# --- Assessment Integration (Merged) ---




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
    topic_uid: Optional[str] = None
    user_context: UserContext
    goal_type: Optional[GoalType] = None
    curriculum_code: Optional[str] = None

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

def _topic_accessible(subject_uid: str, topic_uid: str, resolved_level: int, goal_type: Optional[str] = None) -> bool:
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
        
        # If goal is exam, we allow reviewing past material (ignore mx check)
        if goal_type != "exam":
            if isinstance(mx, (int, float)):
                ok = ok and resolved_level <= int(mx)
        return ok
    except Exception:
        return True


async def _generate_question_llm(topic_uid: str, exclude_uids: set, is_visual: bool = False, previous_prompts: List[str] = [], difficulty: int = 5) -> Dict:
    # 1. Get Topic Context (Title, Description, Prerequisites, Subject, Skills)
    repo = None
    topic_context = {
        "title": topic_uid,
        "description": "",
        "prereqs": [],
        "subject": "",
        "skills": []
    }
    
    try:
        repo = Neo4jRepo()
        def _get_context(tx):
            query = """
            MATCH (t:Topic {uid: $uid})
            OPTIONAL MATCH (t)-[:PREREQ]->(p:Topic)
            OPTIONAL MATCH (t)-[:REQUIRES_SKILL]->(s:Skill)
            OPTIONAL MATCH (sub:Subject)-[:CONTAINS*]->(t)
            RETURN 
                t.title as title, 
                t.description as description, 
                collect(DISTINCT p.title) as prereqs, 
                collect(DISTINCT {title: s.title, definition: s.definition}) as skills,
                head(collect(sub.title)) as subject
            """
            res = tx.run(query, uid=topic_uid)
            rec = res.single()
            if rec:
                return {
                    "title": rec["title"] or topic_uid,
                    "description": rec["description"] or "",
                    "prereqs": [p for p in rec["prereqs"] if p],
                    "subject": rec["subject"] or "",
                    "skills": [s for s in rec["skills"] if s and s.get("title")]
                }
            return None
        
        ctx = repo._retry(lambda s: s.read_transaction(_get_context))
        if ctx:
            topic_context = ctx
    except Exception:
        pass
    finally:
        if repo:
            try:
                repo.close()
            except Exception:
                pass

    topic_title = topic_context["title"]
    
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
    - Canvas: 8x8 grid. Coordinates x:[0,8], y:[0,8].
    - Center objects at (5,5). Max 3 objects.
    - "visualization" structure:
      {
        "type": "geometric_shape" | "graph" | "diagram",
        "coordinates": [ 
            // Array of shape objects. ALWAYS use array of objects.
            { "type": "polygon", "points": [{"x":..., "y":...}], "label": "ABC", "color": "..." },
            { "type": "line", "points": [{"x":..., "y":...}], "label": "a" },
            { "type": "point", "x": ..., "y": ..., "label": "B", "color": "red" }
        ],
        "indicators": [
            { "type": "dimension", "start": {"x":..., "y":...}, "end": {"x":..., "y":...}, "text": "5 cm" }
        ]
      }
    - CRITICAL: For single points (like "Point B"), USE "type": "point" with "x", "y" directly. DO NOT use "type": "line" for a point!
    - CRITICAL: For FUNCTIONS and CURVES (e.g. parabolas, circles, sine waves):
      - USE "type": "line" (or "path").
      - MUST generate AT LEAST 10-20 points to make the curve look smooth. 
      - DO NOT use "type": "polygon" for open curves (like parabolas).
      - Example Parabola: [{"x": -3, "y": 9}, {"x": -2, "y": 4}, {"x": -1, "y": 1}, {"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 4}, {"x": 3, "y": 9}]
    - CRITICAL: Coordinates MUST be mathematically consistent with the problem statement values.
    - ACCURACY RULE: If the problem involves a function (e.g. y = 2x - 1), YOU MUST CALCULATE the y-coordinates correctly for the given x-coordinates.
      Example: If y = 2x - 1 and x = 3, then y MUST be 5.
    - PREFERENCE: Use integer coordinates (e.g. x=2, y=3) or simple decimals (x=2.5) to avoid precision errors. DO NOT use long random floats.
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

    # Enhanced Context for LLM
    description_text = f"Topic Description: {topic_context['description']}" if topic_context['description'] else ""
    prereqs_text = f"Prerequisites: {', '.join(topic_context['prereqs'])}" if topic_context['prereqs'] else ""
    subject_text = f"Subject/Domain: {topic_context['subject']}" if topic_context['subject'] else ""
    
    skills_text = ""
    if topic_context['skills']:
        skills_text = "Related Skills/Methods:\n" + "\n".join([f"- {s['title']}: {s.get('definition', '')}" for s in topic_context['skills']])

    prompt_text = f"""
    Generate a unique assessment question for the topic "{topic_title}" (UID: {topic_uid}).
    {subject_text}
    {description_text}
    {prereqs_text}
    {skills_text}
    
    Context: Adaptive learning platform.
    Target Audience: High school / University students.
    Language: Russian.
    
    Difficulty Level: {difficulty}/10 ({diff_desc}).
    - Level 1-3: Basic definition, simple recognition, 1-step problems.
    - Level 4-7: Standard problems, application of formula, 2-step reasoning.
    - Level 8-10: Complex problems, synthesis of concepts, edge cases, multi-step.
    
    CRITICAL INSTRUCTION:
    If the topic is simple (e.g. "Multiplication Table") but the Difficulty Level is High (8-10), DO NOT generate simple questions (like "2*2"). 
    Instead, generate complex problems involving the topic, such as:
    - Word problems applying the concept.
    - Reverse problems (find factors).
    - Multi-step equations.
    - Conceptual questions about properties (distributivity, etc.).
    
    Question Type: {q_type}
    Is Visual Task: {is_visual}
    {visual_instruction}
    {avoid_context}
    
    IMPORTANT: If "Is Visual Task" is True, you MUST provide a valid "visualization" object in the JSON.
    The "visualization" object MUST have a "type" (one of: geometric_shape, graph, diagram, chart) and "coordinates".
    
    IMPORTANT: If "Is Visual Task" is False, you MUST NOT refer to any pictures, figures, or drawings in the question text.
    The question must be purely textual and solvable without any visual aid.
    
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
    
    # Retry loop to enforce visual consistency
    data = {}
    content = ""
    for attempt in range(2):
        try:
            res = await openai_chat_async(messages, temperature=0.9)
            if not res.get("ok"):
                 raise Exception("LLM generation failed")
            
            content = res.get("content", "")
            raw_content = content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            # Validation: check for visual references in text when is_visual is False
            is_vis_gen = data.get("is_visual", False)
            prompt_gen = data.get("prompt", "")
            
            # Regex for visual references
            visual_ref_pattern = r"(?i)(на\s+)?(рисун|чертеж|схем)(к|ке|ка|е|а|ок)|(см\.|смотри)\s+рис|изображен(ы|о|а)?|shown\s+in\s+(the\s+)?figure|see\s+figure"
            has_visual_ref = bool(re.search(visual_ref_pattern, prompt_gen))
            
            if not is_vis_gen and has_visual_ref:
                if attempt < 1:
                    print(f"Retry LLM: is_visual=False but text has visual ref: {prompt_gen[:50]}...")
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": "You set 'is_visual': false, but the text refers to a figure ('drawing', 'shown', etc.). Please regenerate the question to be PURELY textual, without any reference to an image."})
                    continue
                else:
                    # Second failure: Force clean up
                    print("LLM failed consistency check twice. Stripping visual refs.")
                    clean_prompt = re.sub(visual_ref_pattern, "", prompt_gen).strip()
                    if clean_prompt:
                         clean_prompt = clean_prompt[0].upper() + clean_prompt[1:]
                    data["prompt"] = clean_prompt
            
            # Success
            break
            
        except Exception as e:
            if attempt == 1: raise e
            print(f"LLM parsing error: {e}, retrying...")
            pass
        
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
                vis = data["visualization"]
                vis_type = vis.get("type")
                
                # Check if type is valid
                valid_type = VisualizationType.GEOMETRIC_SHAPE # Default
                try:
                    if vis_type:
                        valid_type = VisualizationType(vis_type)
                except ValueError:
                    # Fallback for common mismatches
                    if vis_type == "chart": valid_type = VisualizationType.CHART
                    elif vis_type == "diagram": valid_type = VisualizationType.DIAGRAM
                    elif vis_type == "graph": valid_type = VisualizationType.GRAPH
                
                vis["type"] = valid_type.value

                # Integrations with GeometryEngine for valid coordinates
                if valid_type in [VisualizationType.GEOMETRIC_SHAPE, VisualizationType.GRAPH, VisualizationType.DIAGRAM]:
                    try:
                        coords = vis.get("coordinates")
                        
                        # 1. Standardize input to list of shape objects
                        if isinstance(coords, list) and len(coords) > 0:
                            first_elem = coords[0]
                            # Detect "Mode 1" (list of points) and convert to "Mode 2" (list of shapes)
                            if isinstance(first_elem, dict) and "x" in first_elem and "y" in first_elem and "points" not in first_elem:
                                coords = [{"type": "polygon", "points": coords, "label": "Generated"}]
                        
                        # 2. Normalize to 10x10 canvas
                        # GeometryEngine.normalize handles list of shapes
                        normalized_coords = GeometryEngine.normalize(coords)
                        
                        # 3. Validate
                        GeometryEngine.validate(normalized_coords)
                        
                        # 4. Update visualization object
                        vis["coordinates"] = normalized_coords
                        
                    except Exception as geo_err:
                        print(f"GeometryEngine error (using original coords): {geo_err}")
                        # If normalization fails, we attempt to use original coordinates if they are somewhat valid
                        pass

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
    "/assessment/start",
    response_model=StandardResponse,
    responses={400: {"model": ApiError}, 404: {"model": ApiError}},
)
async def start(payload: StartRequest) -> Dict:
    try:
        # Resolve topic_uid if missing (e.g. for Exam mode starting from first topic)
        if not payload.topic_uid:
            if payload.curriculum_code:
                cv = get_graph_view(payload.curriculum_code)
                if cv.get("ok") and cv.get("nodes"):
                    # Pick the first topic from the curriculum
                    # nodes are ordered by order_index
                    for n in cv["nodes"]:
                        if n.get("canonical_uid"):
                            payload.topic_uid = n["canonical_uid"]
                            break
            
            if not payload.topic_uid:
                raise HTTPException(status_code=400, detail="topic_uid is required (or valid curriculum_code with topics)")

        uc = payload.user_context or UserContext()
        resolved = _resolve_level(uc)
        if not _topic_accessible(payload.subject_uid, payload.topic_uid, resolved, payload.goal_type):
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
            "goal_type": payload.goal_type,
            "curriculum_code": payload.curriculum_code,
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
    "/assessment/next",
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
                    
                    # Normalized score for mastery consistency
                    normalized_score = final_percentage / 100.0

                    # Detailed analytics
                    detailed_analytics = {
                        "gaps": llm_analytics.get("specific_gaps", gaps),
                        "recommended_focus": llm_analytics.get("recommendation", "Повторить теорию и пройти практику 'We Do'" if score < 0.7 else "Закрепить успех практикой"),
                        "strength": "Хорошая скорость ответов" if score > 0.8 else "Внимательность к деталям",
                        "current_percentage": final_percentage,
                        "topic_breakdown": [
                            {"subtopic": "Theory", "mastery": min(100, int(final_percentage * 1.1))},
                            {"subtopic": "Practice", "mastery": int(final_percentage)},
                            {"subtopic": "Application", "mastery": int(final_percentage * 0.9)}
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
                                "mastery": {"score": round(normalized_score, 2)},
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
