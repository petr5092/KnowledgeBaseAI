from typing import List
from pydantic import BaseModel, Field
import json
import asyncio
from app.config.settings import settings
from app.services.kb.jsonl_io import load_jsonl, get_path
from app.services.graph.neo4j_repo import Neo4jRepo

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
    oai = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
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

async def populate_graph():
    repo = Neo4jRepo()
    print("Connected to Neo4j")

    # 1. Subjects
    subjects = load_jsonl(get_path('subjects.jsonl'))
    print(f"Loading {len(subjects)} subjects...")
    for s in subjects:
        params = s.copy()
        params.setdefault('tenant_id', 'default')
        params.setdefault('description', '')
        repo.write("""
            MERGE (s:Subject {uid: $uid})
            SET s.title = $title, 
                s.tenant_id = $tenant_id,
                s.description = $description
        """, params)

    # 2. Sections
    sections = load_jsonl(get_path('sections.jsonl'))
    print(f"Loading {len(sections)} sections...")
    for s in sections:
        params = s.copy()
        params.setdefault('description', '')
        repo.write("""
            MERGE (s:Section {uid: $uid})
            SET s.title = $title, s.description = $description
            WITH s
            MATCH (sub:Subject {uid: $subject_uid})
            MERGE (sub)-[:CONTAINS]->(s)
        """, params)

    # 3. Subsections
    subsections = load_jsonl(get_path('subsections.jsonl'))
    print(f"Loading {len(subsections)} subsections...")
    for s in subsections:
        params = s.copy()
        params.setdefault('description', '')
        repo.write("""
            MERGE (s:Subsection {uid: $uid})
            SET s.title = $title, s.description = $description
            WITH s
            MATCH (sec:Section {uid: $section_uid})
            MERGE (sec)-[:CONTAINS]->(s)
        """, params)

    # 4. Topics
    topics = load_jsonl(get_path('topics.jsonl'))
    print(f"Loading {len(topics)} topics...")
    for t in topics:
        params = t.copy()
        params.setdefault('description', '')
        params.setdefault('user_class_min', None)
        params.setdefault('user_class_max', None)
        params.setdefault('difficulty_band', 'standard')
        repo.write("""
            MERGE (t:Topic {uid: $uid})
            SET t.title = $title, 
                t.description = $description,
                t.user_class_min = $user_class_min,
                t.user_class_max = $user_class_max,
                t.difficulty_band = $difficulty_band
            WITH t
            MATCH (sub:Subsection {uid: $section_uid})
            MERGE (sub)-[:CONTAINS]->(t)
        """, params)
        
    # 5. Skills
    skills = load_jsonl(get_path('skills.jsonl'))
    print(f"Loading {len(skills)} skills...")
    for s in skills:
        params = s.copy()
        params.setdefault('definition', '')
        repo.write("""
            MERGE (s:Skill {uid: $uid})
            SET s.title = $title, s.definition = $definition
        """, params)
        
    # 6. Topic-Skills
    topic_skills = load_jsonl(get_path('topic_skills.jsonl'))
    print(f"Loading {len(topic_skills)} topic-skill links...")
    for ts in topic_skills:
        params = ts.copy()
        params.setdefault('weight', 'linked')
        params.setdefault('confidence', 1.0)
        repo.write("""
            MATCH (t:Topic {uid: $topic_uid})
            MATCH (s:Skill {uid: $skill_uid})
            MERGE (t)-[r:REQUIRES_SKILL]->(s)
            SET r.weight = $weight, r.confidence = $confidence
        """, params)

    # 7. Content Units
    units = load_jsonl(get_path('content_units.jsonl'))
    print(f"Loading {len(units)} content units...")
    for u in units:
        payload_str = json.dumps(u.get('payload', {}), ensure_ascii=False)
        params = {
            'uid': u['uid'],
            'topic_uid': u['topic_uid'],
            'branch': u.get('branch', 'theory'),
            'type': u.get('type', 'concept'),
            'complexity': u.get('complexity', 0.5),
            'payload': payload_str
        }
        repo.write("""
            MERGE (u:ContentUnit {uid: $uid})
            SET u.branch = $branch, u.type = $type, u.complexity = $complexity, u.payload = $payload
            WITH u
            MATCH (t:Topic {uid: $topic_uid})
            MERGE (t)-[:HAS_UNIT]->(u)
        """, params)

    print("Graph population completed.")

if __name__ == "__main__":
    print("Starting population script...")
    asyncio.run(populate_graph())
