from typing import List
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
import instructor
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

client = instructor.from_openai(AsyncOpenAI(api_key=settings.openai_api_key), mode=instructor.Mode.JSON_SCHEMA)

async def generate_concepts_and_skills(topic: str, language: str) -> GeneratedBundle:
    messages = [
        {"role": "system", "content": "Return structured JSON for concepts and skills in the target language."},
        {"role": "user", "content": f"topic={topic}; lang={language}"},
    ]
    resp = await client.chat.completions.create(model="gpt-4o-mini", messages=messages, response_model=GeneratedBundle)
    return resp
