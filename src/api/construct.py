from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List
from src.services.ai_engine.ai_engine import generate_concepts_and_skills
from src.services.vector.chroma_service import embed_text, upsert_concept, query_similar

router = APIRouter(prefix="/v1/construct")

class MagicFillInput(BaseModel):
    topic_uid: str
    topic_title: str
    language: str = "ru"

@router.post("/magic_fill")
async def magic_fill(payload: MagicFillInput) -> Dict:
    bundle = await generate_concepts_and_skills(payload.topic_title, payload.language)
    created: List[Dict] = []
    for c in bundle.concepts:
        emb = await embed_text(c.title + " " + c.definition)
        sims = query_similar(emb, top_k=3)
        if sims and sims[0][1] >= 0.92:
            created.append({"merged_into": sims[0][0], "title": c.title})
        else:
            uid = f"CN-{payload.topic_uid}-{abs(hash(c.title))%100000}"
            await upsert_concept(uid, c.title, c.definition, emb)
            created.append({"created": uid, "title": c.title})
    return {"ok": True, "results": created}
