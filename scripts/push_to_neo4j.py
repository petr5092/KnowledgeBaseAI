#!/usr/bin/env python3
import os
import json
from typing import List, Dict
from neo4j import GraphDatabase

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KB_DIR = os.path.join(BASE_DIR, 'kb')

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j')


def load_jsonl(filename: str) -> List[Dict]:
    path = os.path.join(KB_DIR, filename)
    data: List[Dict] = []
    if not os.path.exists(path):
        return data
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data


def apply_constraints(session):
    queries = [
        "CREATE CONSTRAINT subject_uid IF NOT EXISTS FOR (s:Subject) REQUIRE s.uid IS UNIQUE",
        "CREATE CONSTRAINT section_uid IF NOT EXISTS FOR (s:Section) REQUIRE s.uid IS UNIQUE",
        "CREATE CONSTRAINT topic_uid IF NOT EXISTS FOR (t:Topic) REQUIRE t.uid IS UNIQUE",
        "CREATE CONSTRAINT skill_uid IF NOT EXISTS FOR (s:Skill) REQUIRE s.uid IS UNIQUE",
        "CREATE CONSTRAINT method_uid IF NOT EXISTS FOR (m:Method) REQUIRE m.uid IS UNIQUE",
        "CREATE CONSTRAINT example_uid IF NOT EXISTS FOR (e:Example) REQUIRE e.uid IS UNIQUE",
        "CREATE CONSTRAINT error_uid IF NOT EXISTS FOR (e:Error) REQUIRE e.uid IS UNIQUE",
    ]
    for q in queries:
        session.run(q)


def merge_nodes(session, label: str, items: List[Dict], prop_map: Dict[str, str]):
    if not items:
        return
    # Build lightweight dicts with only known properties
    prepared = []
    for it in items:
        node = {"uid": it.get("uid")}
        for k_src, k_dst in prop_map.items():
            if k_src in it:
                node[k_dst] = it[k_src]
        prepared.append(node)
    session.run(
        f"""
        UNWIND $rows AS row
        MERGE (n:{label} {{uid: row.uid}})
        SET n += row
        """,
        rows=prepared,
    )


def create_relationships(session, query: str, rows: List[Dict]):
    if not rows:
        return
    session.run(query, rows=rows)


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # Constraints
        apply_constraints(session)

        # Cleanup non-hierarchical relations to enforce strict hierarchy
        session.run("MATCH ()-[r:USES_SKILL]->() DELETE r")
        session.run("MATCH (:Subject)-[r:HAS_SKILL]->(:Skill) DELETE r")

        # Load data
        subjects = load_jsonl('subjects.jsonl')
        sections = load_jsonl('sections.jsonl')
        topics = load_jsonl('topics.jsonl')
        skills = load_jsonl('skills.jsonl')
        methods = load_jsonl('methods.jsonl')
        examples = load_jsonl('examples.jsonl')
        errors = load_jsonl('errors.jsonl')
        skill_methods = load_jsonl('skill_methods.jsonl')
        skill_topics = load_jsonl('skill_topics.jsonl')
        theories = load_jsonl('theories.jsonl')
        lesson_steps = load_jsonl('lesson_steps.jsonl')
        example_skills = load_jsonl('example_skills.jsonl')

        # Nodes
        merge_nodes(session, 'Subject', subjects, {"title": "title", "description": "description"})
        merge_nodes(session, 'Section', sections, {"title": "title", "description": "description", "order_index": "order_index", "subject_uid": "subject_uid"})
        merge_nodes(session, 'Topic', topics, {
            "title": "title",
            "description": "description",
            "accuracy_threshold": "accuracy_threshold",
            "critical_errors_max": "critical_errors_max",
            "median_time_threshold_seconds": "median_time_threshold_seconds",
            "section_uid": "section_uid",
        })
        merge_nodes(session, 'Skill', skills, {"title": "title", "description": "description", "subject_uid": "subject_uid", "applicability_types": "applicability_types"})
        merge_nodes(session, 'Method', methods, {"title": "title", "method_text": "method_text", "applicability_types": "applicability_types"})
        merge_nodes(session, 'Example', examples, {"title": "title", "statement": "statement", "difficulty_level": "difficulty_level", "subject_uid": "subject_uid", "topic_uid": "topic_uid"})
        merge_nodes(session, 'Error', errors, {"title": "title", "description": "description", "error_type": "error_type"})
        merge_nodes(session, 'Theory', theories, {"title": "title", "content": "content", "section_uid": "section_uid", "topic_uid": "topic_uid"})
        merge_nodes(session, 'LessonStep', lesson_steps, {"step_type": "step_type", "order_index": "order_index", "topic_uid": "topic_uid", "section_uid": "section_uid", "resource_uids": "resource_uids", "skill_uids": "skill_uids"})

        # Relationships
        # Subject -> Section
        rel_subject_section = [{"subject_uid": s.get("subject_uid"), "section_uid": s.get("uid")} for s in sections if s.get("subject_uid")]
        create_relationships(session, 
            """
            UNWIND $rows AS row
            MATCH (sub:Subject {uid: row.subject_uid})
            MATCH (sec:Section {uid: row.section_uid})
            MERGE (sub)-[:HAS_SECTION]->(sec)
            """,
            rel_subject_section)

        # Section -> Topic
        rel_section_topic = [{"section_uid": t.get("section_uid"), "topic_uid": t.get("uid")} for t in topics if t.get("section_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (sec:Section {uid: row.section_uid})
            MATCH (top:Topic {uid: row.topic_uid})
            MERGE (sec)-[:HAS_TOPIC]->(top)
            """,
            rel_section_topic)

        # Subject -> Skill (removed to keep strict hierarchy per requirements)

        # Skill -> Method (from skill_methods.jsonl)
        rel_skill_method = [{
            "skill_uid": sm.get("skill_uid"),
            "method_uid": sm.get("method_uid"),
            "weight": sm.get("weight", "secondary"),
            "confidence": sm.get("confidence", 0.5),
            "is_auto_generated": sm.get("is_auto_generated", False)
        } for sm in skill_methods if sm.get("skill_uid") and sm.get("method_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (sk:Skill {uid: row.skill_uid})
            MATCH (m:Method {uid: row.method_uid})
            MERGE (sk)-[r:HAS_METHOD]->(m)
            SET r.weight = row.weight, r.confidence = row.confidence, r.is_auto_generated = row.is_auto_generated
            """,
            rel_skill_method)

        # Topic -> Skill (from skill_topics.jsonl)
        rel_topic_skill = [{
            'topic_uid': st.get('topic_uid'),
            'skill_uid': st.get('skill_uid'),
            'weight': st.get('weight', 'secondary'),
            'confidence': st.get('confidence', 0.5)
        } for st in skill_topics if st.get('topic_uid') and st.get('skill_uid')]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (t:Topic {uid: row.topic_uid})
            MATCH (s:Skill {uid: row.skill_uid})
            MERGE (t)-[r:REQUIRES_SKILL]->(s)
            SET r.weight = row.weight, r.confidence = row.confidence
            """,
            rel_topic_skill)

        # Section -> Theory and Topic -> Theory
        rel_section_theory = [{"section_uid": th.get("section_uid"), "theory_uid": th.get("uid")} for th in theories if th.get("section_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (sec:Section {uid: row.section_uid})
            MATCH (th:Theory {uid: row.theory_uid})
            MERGE (sec)-[:HAS_THEORY]->(th)
            """,
            rel_section_theory)

        rel_topic_theory = [{"topic_uid": th.get("topic_uid"), "theory_uid": th.get("uid")} for th in theories if th.get("topic_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (top:Topic {uid: row.topic_uid})
            MATCH (th:Theory {uid: row.theory_uid})
            MERGE (top)-[:HAS_THEORY]->(th)
            """,
            rel_topic_theory)

        # Skill -> Example links (inverse of previous to enforce Topic -> Skills -> Examples)
        rel_skill_example = [{"example_uid": es.get("example_uid"), "skill_uid": es.get("skill_uid")} for es in example_skills if es.get("example_uid") and es.get("skill_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (sk:Skill {uid: row.skill_uid})
            MATCH (ex:Example {uid: row.example_uid})
            MERGE (sk)-[:HAS_EXAMPLE]->(ex)
            """,
            rel_skill_example)

        # Topic -> LessonStep and Step -> resource links (Theory/Example/Method)
        rel_topic_step = [{"topic_uid": st.get("topic_uid"), "step_uid": st.get("uid")} for st in lesson_steps if st.get("topic_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (top:Topic {uid: row.topic_uid})
            MATCH (ls:LessonStep {uid: row.step_uid})
            MERGE (top)-[:HAS_STEP]->(ls)
            """,
            rel_topic_step)

        # Step -> resources (by UID dispatch)
        # We will attempt to match against Theory, Example and Method labels
        for st in lesson_steps:
            res_uids = st.get('resource_uids') or []
            for ruid in res_uids:
                session.run(
                    """
                    MATCH (ls:LessonStep {uid: $step_uid})
                    OPTIONAL MATCH (th:Theory {uid: $ruid})
                    OPTIONAL MATCH (ex:Example {uid: $ruid})
                    OPTIONAL MATCH (m:Method {uid: $ruid})
                    FOREACH (_ IN CASE WHEN th IS NULL THEN [] ELSE [1] END |
                        MERGE (ls)-[:USES_RESOURCE]->(th)
                    )
                    FOREACH (_ IN CASE WHEN ex IS NULL THEN [] ELSE [1] END |
                        MERGE (ls)-[:USES_RESOURCE]->(ex)
                    )
                    FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END |
                        MERGE (ls)-[:USES_RESOURCE]->(m)
                    )
                    """,
                    step_uid=st.get('uid'), ruid=ruid
                )

        # Subject -> Example
        rel_subject_example = [{"subject_uid": e.get("subject_uid"), "example_uid": e.get("uid")} for e in examples if e.get("subject_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (sub:Subject {uid: row.subject_uid})
            MATCH (ex:Example {uid: row.example_uid})
            MERGE (sub)-[:HAS_EXAMPLE]->(ex)
            """,
            rel_subject_example)

        # Topic -> Example
        rel_topic_example = [{"topic_uid": e.get("topic_uid"), "example_uid": e.get("uid")} for e in examples if e.get("topic_uid")]
        create_relationships(session,
            """
            UNWIND $rows AS row
            MATCH (top:Topic {uid: row.topic_uid})
            MATCH (ex:Example {uid: row.example_uid})
            MERGE (top)-[:HAS_EXAMPLE]->(ex)
            """,
            rel_topic_example)

    driver.close()
    print('Neo4j import complete')


if __name__ == '__main__':
    main()