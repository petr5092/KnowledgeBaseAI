from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from app.services.graph.neo4j_repo import relation_context, neighbors, get_node_details
from app.config.settings import settings
from app.services.roadmap_planner import plan_route
from app.services.questions import select_examples_for_topics, all_topic_uids_from_examples
from app.api.common import ApiError, StandardResponse
from app.core.context import get_tenant_id
from app.schemas.roadmap import RoadmapRequest
from app.services.reasoning.gaps import compute_gaps
from app.services.reasoning.next_best_topic import next_best_topics
from app.services.reasoning.mastery_update import update_mastery

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

class RoadmapItem(BaseModel):
    uid: str
    title: Optional[str] = None
    mastered: float
    missing_prereqs: int
    priority: float

class RoadmapResponse(BaseModel):
    items: List[RoadmapItem]

@router.post("/roadmap", summary="Build adaptive roadmap", response_model=RoadmapResponse)
async def roadmap(payload: RoadmapRequest) -> Dict:
    # Use unified request model
    items = plan_route(payload.subject_uid, payload.current_progress or {}, payload.limit, 0.15, tenant_id=get_tenant_id())
    return {"items": items}

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
