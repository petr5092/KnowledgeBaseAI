from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from typing import Dict, List
from app.services.kb.builder import generate_subject_openai_async
from app.services.graph.utils import sync_from_jsonl, compute_static_weights, analyze_knowledge
from app.api.deps import require_admin

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin), Security(HTTPBearer())], tags=["Админка: генерация"])

class GenerateSubjectInput(BaseModel):
    subject_uid: str
    subject_title: str
    language: str = "ru"
    domain_context: str = "Academic Subject"
    sections_seed: List[str] | None = None
    topics_per_section: int = 6
    skills_per_topic: int = 3
    methods_per_skill: int = 2
    examples_per_topic: int = 3
    concurrency: int = 4

@router.post("/generate_subject", summary="Генерация предмета (LLM)", description="Генерирует структуру предмета через OpenAI и возвращает результат генерации.")
async def generate_subject(payload: GenerateSubjectInput) -> Dict:
    """
    Принимает:
      - subject_uid: UID предмета
      - subject_title: название предмета
      - language: язык генерации
      - domain_context: контекст (например, "Academic Subject", "Corporate Manual")
      - параметры глубины генерации: sections_seed, topics_per_section, skills_per_topic, methods_per_skill, examples_per_topic, concurrency

    Возвращает:
      - объект результата генерации (асинхронные результаты по шагам)
    """
    res = await generate_subject_openai_async(
        payload.subject_uid,
        payload.subject_title,
        payload.language,
        domain_context=payload.domain_context,
        sections_seed=payload.sections_seed,
        topics_per_section=payload.topics_per_section,
        skills_per_topic=payload.skills_per_topic,
        methods_per_skill=payload.methods_per_skill,
        examples_per_topic=payload.examples_per_topic,
        concurrency=payload.concurrency,
    )
    return res
