from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Set
import json
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

class LessonUnit(BaseModel):
    uid: str
    type: str  # i_do, we_do, you_do, test
    title: str
    payload: Dict[str, Any]

class MicroLesson(BaseModel):
    order: int
    title: str
    i_do: Optional[LessonUnit] = None
    we_do: Optional[LessonUnit] = None
    you_do: Optional[LessonUnit] = None

class RoadmapNode(BaseModel):
    topic_uid: str
    title: str
    description: Optional[str] = None
    status: str = "locked"  # locked, available, completed
    max_score: int = 0
    current_score: float = 0.0
    progress_percentage: float = 0.0
    units: List[MicroLesson] = []
    final_test: Optional[LessonUnit] = None

class RoadmapResponse(BaseModel):
    max_score: int = 0
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
            WITH t, path
            
            WITH t, path,
                 CASE 
                   WHEN t.uid = $focus THEN 'self'
                   WHEN path IS NOT NULL AND startNode(path) = t THEN 'prerequisite'
                   WHEN path IS NOT NULL AND endNode(path) = t THEN 'dependent'
                   ELSE 'related'
                 END AS rel_type,
                 length(path) as dist
            
            OPTIONAL MATCH (t)-[:HAS_UNIT]->(u:ContentUnit)
            OPTIONAL MATCH (t)-[:PREREQ]->(p:Topic)
            WITH t, rel_type, dist, collect({uid: u.uid, type: u.type, payload: u.payload, complexity: u.complexity}) AS units, collect(p.uid) as prereqs
            
            RETURN t.uid AS uid, t.title AS title, t.description AS description, units, prereqs, rel_type, dist
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
            OPTIONAL MATCH (t)-[:HAS_UNIT]->(u:ContentUnit)
            OPTIONAL MATCH (t)-[:PREREQ]->(p:Topic)
            WITH t, collect({uid: u.uid, type: u.type, payload: u.payload, complexity: u.complexity}) AS units, collect(p.uid) as prereqs
            RETURN t.uid AS uid, t.title AS title, t.description AS description, units, prereqs
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
            "prerequisites": r.get("prereqs", [])
        })

    used_llm = False
    if settings.openai_api_key and candidates_info:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
            
            prompt = (
                "You are an adaptive learning AI. Select the best 8 topics for a student roadmap from the list below.\n"
                f"The student is currently focusing on topic: '{focus_title}' (UID: {focus_uid}).\n"
                "Rules for Roadmap Construction:\n"
                "1. **REMEDIATION (Score < 0.6)**: If the focus topic is failed or new, select 'prerequisite' topics.\n"
                "   - **CRITICAL**: Prioritize IMMEDIATE prerequisites (distance=1). DO NOT jump to distant/basic topics (distance > 1) unless immediate ones are also failed.\n"
                "   - Example: If 'Quadratic Equations' is failed, choose 'Polynomials' (dist=1), NOT 'Addition' (dist=3).\n"
                "2. **FOCUS LOOP (Score 0.6 - 0.85)**: If score is 0.6-0.85, prioritize THE FOCUS TOPIC ITSELF ('self') to close gaps.\n"
                "3. **PROGRESSION (Score > 0.85)**: Only if the focus topic is FULLY MASTERED (>0.85), suggest 'dependent' topics (next steps).\n"
                "4. If no focus topic is provided, prioritize Remediation -> Foundation -> New Topics.\n"
                "5. GENERATE a short, engaging description (in Russian) for any topic that has an empty description.\n"
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
            
        # Categorize units
        raw_units = r.get("units", [])
        
        # Helper to parse payload
        def get_payload(u):
            p = u.get("payload")
            if isinstance(p, str):
                try:
                    return json.loads(p)
                except:
                    return {}
            return p if p else {}

        # Group units into MicroLessons
        lessons_map: Dict[int, Dict[str, Any]] = {} # order -> {title: "", i_do: ..., we_do: ..., you_do: ...}
        final_test_unit = None
        
        for u in raw_units:
            u_type = u.get("type")
            p = get_payload(u)
            
            if u_type == "lesson_test":
                final_test_unit = LessonUnit(
                    uid=u["uid"],
                    type="lesson_test",
                    title="Финальный тест",
                    payload=p
                )
                continue
                
            if u_type in ["lesson_i_do", "lesson_we_do", "lesson_you_do"]:
                order = p.get("order", 1)
                
                if order not in lessons_map:
                    # Try to find a title from any unit in this group, usually I_DO has the main title
                    lessons_map[order] = {"order": order, "title": f"Урок {order}"}
                
                # Update title if present in micro_lesson_title
                if "micro_lesson_title" in p:
                    lessons_map[order]["title"] = p["micro_lesson_title"]
                
                l_unit = LessonUnit(
                    uid=u["uid"],
                    type=u_type,
                    title="", # Will be set by frontend or implied by field
                    payload=p
                )
                # Assign friendly title based on type
                if u_type == "lesson_i_do":
                    l_unit.title = "Изучение (I Do)"
                    lessons_map[order]["i_do"] = l_unit
                elif u_type == "lesson_we_do":
                    l_unit.title = "Практика (We Do)"
                    lessons_map[order]["we_do"] = l_unit
                elif u_type == "lesson_you_do":
                    l_unit.title = "Задание (You Do)"
                    lessons_map[order]["you_do"] = l_unit

        # Convert map to list and sort
        lessons_list = []
        for order, data in lessons_map.items():
            lessons_list.append(MicroLesson(
                order=order,
                title=data["title"],
                i_do=data.get("i_do"),
                we_do=data.get("we_do"),
                you_do=data.get("you_do")
            ))
        
        lessons_list.sort(key=lambda x: x.order)
        
        # Calculate max_score
        # 1 point per micro-lesson (if fully completed i/we/you? or 1 per unit?)
        # Let's keep 1 point per unit for simplicity, so max_score = sum of units
        node_score = 0
        if final_test_unit:
            node_score += 3
        for l in lessons_list:
            if l.i_do: node_score += 1
            if l.we_do: node_score += 1
            if l.you_do: node_score += 1
        
        current_score = p_val * node_score
        progress_percentage = p_val * 100.0

        topics.append(RoadmapNode(
            topic_uid=t_uid,
            title=r["title"],
            description=r.get("description"),
            status=status,
            max_score=node_score,
            current_score=current_score,
            progress_percentage=progress_percentage,
            units=lessons_list,
            final_test=final_test_unit
        ))
        count += 1

    total_roadmap_score = sum(n.max_score for n in topics)
    return {"nodes": topics, "max_score": total_roadmap_score}

# --- Knowledge / Topics ---

class TopicsAvailableRequest(BaseModel):
    subject_uid: Optional[str] = None
    subject_title: Optional[str] = None
    user_context: UserContext
    curriculum_code: Optional[str] = None

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
            for r in rows or []:
                mn = r.get("user_class_min")
                mx = r.get("user_class_max")
                ok = True
                if isinstance(mn, (int, float)):
                    ok = ok and resolved >= int(mn)
                if isinstance(mx, (int, float)):
                    ok = ok and resolved <= int(mx)
                
                # Curriculum Whitelist Check
                if allowed_topics is not None and r.get("topic_uid") not in allowed_topics:
                    ok = False

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
            for r in rows or []:
                if allowed_topics is not None and r.get("topic_uid") not in allowed_topics:
                    continue
                topics.append(
                    {
                        "topic_uid": r.get("topic_uid"),
                        "title": r.get("title"),
                        "user_class_min": r.get("user_class_min"),
                        "user_class_max": r.get("user_class_max"),
                        "difficulty_band": r.get("difficulty_band") or "standard",
                        "prereq_topic_uids": [p for p in (r.get("prereq_topic_uids") or []) if p],
                    }
                )
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
            for r in rows or []:
                if allowed_topics is not None and r.get("topic_uid") not in allowed_topics:
                    continue
                topics.append(
                    {
                        "topic_uid": r.get("topic_uid"),
                        "title": r.get("title"),
                        "user_class_min": r.get("user_class_min"),
                        "user_class_max": r.get("user_class_max"),
                        "difficulty_band": r.get("difficulty_band") or "standard",
                        "prereq_topic_uids": [p for p in (r.get("prereq_topic_uids") or []) if p],
                    }
                )
            repo.close()
        except Exception:
            ...
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
