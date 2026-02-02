import asyncio
import json
import os
from app.services.graph.neo4j_repo import Neo4jRepo

DATA_DIR = os.path.join(os.path.dirname(__file__), "app/kb/ru/mathematics")

def load_jsonl(filename):
    filepath = os.path.join(DATA_DIR, filename)
    data = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return data

async def load_structure():
    repo = Neo4jRepo()
    print("Connected to Neo4j")
    
    # 1. Create Constraints
    print("Creating constraints...")
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Subject) REQUIRE s.uid IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Section) REQUIRE s.uid IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (ss:Subsection) REQUIRE ss.uid IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.uid IS UNIQUE"
    ]
    for q in constraints:
        repo.write(q)

    # 1.5 Load Subjects
    subjects = load_jsonl('subjects.jsonl')
    print(f"Loading {len(subjects)} subjects...")
    for sub in subjects:
        repo.write("""
            MERGE (s:Subject {uid: $uid})
            SET s.title = $title, s.description = $description
        """, sub)

    # 2. Load Sections
    sections = load_jsonl('sections.jsonl')
    print(f"Loading {len(sections)} sections...")
    for s in sections:
        repo.write("""
            MERGE (s:Section {uid: $uid})
            SET s.title = $title, s.description = $description, s.subject_uid = $subject_uid
            WITH s
            MATCH (sub:Subject {uid: $subject_uid})
            MERGE (sub)-[:CONTAINS]->(s)
        """, s)

    # 3. Load Subsections
    subsections = load_jsonl('subsections.jsonl')
    print(f"Loading {len(subsections)} subsections...")
    for ss in subsections:
        repo.write("""
            MERGE (ss:Subsection {uid: $uid})
            SET ss.title = $title, ss.description = $description
            WITH ss
            MATCH (s:Section {uid: $section_uid})
            MERGE (s)-[:CONTAINS]->(ss)
        """, ss)

    # 4. Load Topics
    topics = load_jsonl('topics.jsonl')
    print(f"Loading {len(topics)} topics...")
    for t in topics:
        repo.write("""
            MERGE (t:Topic {uid: $uid})
            SET t.title = $title, 
                t.description = $description,
                t.user_class_min = $user_class_min,
                t.user_class_max = $user_class_max,
                t.difficulty_band = $difficulty_band
            WITH t
            MATCH (ss:Subsection {uid: $section_uid})
            MERGE (ss)-[:CONTAINS]->(t)
        """, t)

    # 5. Load Prereqs
    prereqs = load_jsonl('topic_prereqs.jsonl')
    print(f"Loading {len(prereqs)} prereqs...")
    for p in prereqs:
        repo.write("""
            MATCH (target:Topic {uid: $target_uid})
            MATCH (prereq:Topic {uid: $prereq_uid})
            MERGE (target)-[:REQUIRES {weight: $weight}]->(prereq)
        """, p)

    # 6. Load Skills
    skills = load_jsonl('skills.jsonl')
    print(f"Loading {len(skills)} skills...")
    for s in skills:
        repo.write("""
            MERGE (s:Skill {uid: $uid})
            SET s.title = $title, 
                s.definition = $definition
        """, s)

    # 7. Load Methods
    methods = load_jsonl('methods.jsonl')
    print(f"Loading {len(methods)} methods...")
    for m in methods:
        repo.write("""
            MERGE (m:Method {uid: $uid})
            SET m.title = $title, 
                m.method_text = $method_text
        """, m)

    # 8. Load Topic-Skills
    topic_skills = load_jsonl('topic_skills.jsonl')
    print(f"Loading {len(topic_skills)} topic-skill links...")
    for ts in topic_skills:
        repo.write("""
            MATCH (t:Topic {uid: $topic_uid})
            MATCH (s:Skill {uid: $skill_uid})
            MERGE (t)-[r:REQUIRES_SKILL]->(s)
            SET r.weight = $weight, r.confidence = $confidence
        """, ts)

    # 9. Load Skill-Methods
    skill_methods = load_jsonl('skill_methods.jsonl')
    print(f"Loading {len(skill_methods)} skill-method links...")
    for sm in skill_methods:
        repo.write("""
            MATCH (s:Skill {uid: $skill_uid})
            MATCH (m:Method {uid: $method_uid})
            MERGE (s)-[r:HAS_METHOD]->(m)
            SET r.weight = $weight, 
                r.confidence = $confidence,
                r.is_auto_generated = $is_auto_generated
        """, sm)

    print("Finished loading structure.")
    repo.close()

if __name__ == "__main__":
    asyncio.run(load_structure())
