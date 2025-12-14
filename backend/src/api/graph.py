from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from src.services.graph.neo4j_repo import relation_context, neighbors
from src.config.settings import settings
from src.services.roadmap_planner import plan_route
from src.services.questions import select_examples_for_topics, all_topic_uids_from_examples

router = APIRouter(prefix="/v1/graph")

class ViewportQuery(BaseModel):
    center_uid: str
    depth: int = 1

@router.get("/viewport")
async def viewport(center_uid: str, depth: int = 1) -> Dict:
    ns, es = neighbors(center_uid, depth=depth)
    return {"nodes": ns, "edges": es, "center_uid": center_uid, "depth": depth}

class ChatInput(BaseModel):
    question: str
    from_uid: str
    to_uid: str

@router.post("/chat")
async def chat(payload: ChatInput) -> Dict:
    try:
        from openai import AsyncOpenAI
        from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
    except Exception:
        raise HTTPException(status_code=503, detail="OpenAI client is not available")

    ctx = relation_context(payload.from_uid, payload.to_uid)
    oai = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    messages = [
        {"role": "system", "content": "You are a graph expert. Explain why the relationship exists using provided metadata."},
        {"role": "user", "content": f"Q: {payload.question}\nFrom: {ctx.get('from_title','')} ({payload.from_uid})\nTo: {ctx.get('to_title','')} ({payload.to_uid})\nRelation: {ctx.get('rel','')}\nProps: {ctx.get('props',{})}"},
    ]

    try:
        resp = await oai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    except AuthenticationError:
        raise HTTPException(status_code=503, detail="OpenAI authentication failed (invalid API key)")
    except RateLimitError:
        raise HTTPException(status_code=503, detail="OpenAI rate limit exceeded")
    except APIConnectionError:
        raise HTTPException(status_code=503, detail="OpenAI is unreachable")
    except APIStatusError as e:
        status = getattr(e, "status_code", None)
        if status and 500 <= int(status) < 600:
            raise HTTPException(status_code=503, detail="OpenAI service error")
        raise HTTPException(status_code=502, detail="OpenAI request failed")
    except Exception:
        raise HTTPException(status_code=502, detail="OpenAI request failed")

    usage = resp.usage or None
    answer = resp.choices[0].message.content if resp.choices else ""
    return {"answer": answer, "usage": (usage.model_dump() if hasattr(usage, 'model_dump') else None), "context": ctx}

class RoadmapInput(BaseModel):
    subject_uid: Optional[str] = None
    progress: Dict[str, float] = {}
    limit: int = 30

@router.post("/roadmap")
async def roadmap(payload: RoadmapInput) -> Dict:
    items = plan_route(payload.subject_uid, payload.progress, limit=payload.limit)
    return {"items": items}

class AdaptiveQuestionsInput(BaseModel):
    subject_uid: Optional[str] = None
    progress: Dict[str, float] = {}
    count: int = 10
    difficulty_min: int = 1
    difficulty_max: int = 5
    exclude: List[str] = []

@router.post("/adaptive_questions")
async def adaptive_questions(payload: AdaptiveQuestionsInput) -> Dict:
    roadmap = plan_route(payload.subject_uid, payload.progress, limit=payload.count * 3)
    topic_uids = [it["uid"] for it in roadmap] or all_topic_uids_from_examples()
    examples = select_examples_for_topics(
        topic_uids=topic_uids,
        limit=payload.count,
        difficulty_min=payload.difficulty_min,
        difficulty_max=payload.difficulty_max,
        exclude_uids=set(payload.exclude),
    )
    return {"questions": examples}
