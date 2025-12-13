from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, List
from src.services.kb.builder import generate_subject_openai_async
from src.services.graph.utils import sync_from_jsonl, compute_static_weights, analyze_knowledge
from src.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])

class GenerateSubjectInput(BaseModel):
    subject_uid: str
    subject_title: str
    language: str = "ru"
    sections_seed: List[str] | None = None
    topics_per_section: int = 6
    skills_per_topic: int = 3
    methods_per_skill: int = 2
    examples_per_topic: int = 3
    concurrency: int = 4

@router.post("/generate_subject")
async def generate_subject(payload: GenerateSubjectInput) -> Dict:
    res = await generate_subject_openai_async(
        payload.subject_uid,
        payload.subject_title,
        payload.language,
        sections_seed=payload.sections_seed,
        topics_per_section=payload.topics_per_section,
        skills_per_topic=payload.skills_per_topic,
        methods_per_skill=payload.methods_per_skill,
        examples_per_topic=payload.examples_per_topic,
        concurrency=payload.concurrency,
    )
    return res

@router.post("/generate_subject_import")
async def generate_subject_import(payload: GenerateSubjectInput) -> Dict:
    gen = await generate_subject_openai_async(
        payload.subject_uid,
        payload.subject_title,
        payload.language,
        sections_seed=payload.sections_seed,
        topics_per_section=payload.topics_per_section,
        skills_per_topic=payload.skills_per_topic,
        methods_per_skill=payload.methods_per_skill,
        examples_per_topic=payload.examples_per_topic,
        concurrency=payload.concurrency,
    )
    stats = sync_from_jsonl()
    weights = compute_static_weights()
    metrics = analyze_knowledge()
    return {"generated": gen, "sync": stats, "weights": weights, "metrics": metrics}
