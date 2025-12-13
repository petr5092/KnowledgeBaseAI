from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List
import uuid
from pydantic import Field

router = APIRouter(prefix="/v1/construct")

class MagicFillInput(BaseModel):
    topic_uid: str
    topic_title: str
    language: str = "ru"

class ProposeInput(BaseModel):
    subject_uid: str | None = None
    text: str = Field(..., min_length=20)
    language: str = "ru"

@router.post("/magic_fill")
async def magic_fill(payload: MagicFillInput) -> Dict:
    try:
        from src.services.ai_engine.ai_engine import generate_concepts_and_skills
    except Exception:
        return {"ok": False, "error": "ai engine not available"}
    bundle = await generate_concepts_and_skills(payload.topic_title, payload.language)
    created: List[Dict] = []
    for c in bundle.concepts:
        try:
            from src.services.vector.qdrant_service import embed_text, query_similar, upsert_concept
            emb = await embed_text(c.title + " " + c.definition)
            sims = query_similar(emb, top_k=3)
        except Exception:
            sims = []
        if sims and sims[0][1] >= 0.92:
            created.append({"merged_into": sims[0][0], "title": c.title})
        else:
            uid = f"CN-{payload.topic_uid}-{abs(hash(c.title))%100000}"
            try:
                from src.services.vector.qdrant_service import upsert_concept
                emb = emb if 'emb' in locals() else []
                await upsert_concept(uid, c.title, c.definition, emb)
            except Exception:
                pass
            created.append({"created": uid, "title": c.title})
    return {"ok": True, "results": created}

@router.post("/magic_fill/queue")
async def magic_fill_queue(payload: MagicFillInput) -> Dict:
    job_id = uuid.uuid4().hex[:12]
    try:
        from arq.connections import RedisSettings, ArqRedis
        redis = await ArqRedis.create(RedisSettings(host='redis', port=6379))
        await redis.enqueue_job('magic_fill_job', job_id, payload.topic_uid, payload.topic_title)
        await redis.close()
    except Exception:
        return {"job_id": job_id, "queued": False}
    return {"job_id": job_id, "ws": f"/ws/progress?job_id={job_id}"}

@router.post("/propose")
async def propose(payload: ProposeInput) -> Dict:
    try:
        from src.services.ai_engine.ai_engine import generate_concepts_and_skills
    except Exception:
        return {"concepts": [], "skills": []}
    bundle = await generate_concepts_and_skills(payload.text, payload.language)
    return {"concepts": [c.model_dump() for c in bundle.concepts], "skills": [s.model_dump() for s in bundle.skills]}
