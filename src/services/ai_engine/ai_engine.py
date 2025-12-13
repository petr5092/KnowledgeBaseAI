from typing import List
from pydantic import BaseModel, Field
import json
from src.core.config import settings

class GeneratedConcept(BaseModel):
    title: str
    definition: str = Field(..., description="Academic definition, <50 words")
    reasoning: str

class GeneratedSkill(BaseModel):
    title: str
    description: str

class GeneratedBundle(BaseModel):
    concepts: List[GeneratedConcept]
    skills: List[GeneratedSkill]

async def generate_concepts_and_skills(topic: str, language: str) -> GeneratedBundle:
    try:
        from openai import AsyncOpenAI
    except Exception:
        return GeneratedBundle(concepts=[], skills=[])
    oai = AsyncOpenAI(api_key=settings.openai_api_key)
    messages = [
        {"role": "system", "content": "Return structured JSON for concepts and skills in the target language."},
        {"role": "user", "content": f"topic={topic}; lang={language}"},
    ]
    resp = await oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    return GeneratedBundle.model_validate(data)
