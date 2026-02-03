
import os
import logging
from typing import Dict, Any, List

from app.services.graph.neo4j_repo import Neo4jRepo
from app.services.kb.jsonl_io import load_jsonl

logger = logging.getLogger(__name__)

# Hardcoded path for now as per current structure
KB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "kb", "ru", "mathematics")

def sync_from_jsonl() -> Dict[str, Any]:
    repo = Neo4jRepo()
    stats = {}
    
    try:
        # 0. Subjects (Base)
        subjects = load_jsonl(os.path.join(KB_ROOT, "subjects.jsonl"))
        logger.info(f"Syncing {len(subjects)} subjects...")
        for s in subjects:
            repo.write("""
                MERGE (s:Subject {uid: $uid})
                SET s.title = $title, s.description = $desc, s.tenant_id = 'default'
            """, {"uid": s["uid"], "title": s.get("title", ""), "desc": s.get("description", "")})
        stats["subjects"] = len(subjects)

        # 1. Sections & Subsections
        sections = load_jsonl(os.path.join(KB_ROOT, "sections.jsonl"))
        for s in sections:
            repo.write("""
                MERGE (sec:Section {uid: $uid})
                SET sec.title = $title
                WITH sec
                MATCH (sub:Subject {uid: $sub_uid})
                MERGE (sub)-[:HAS_SECTION]->(sec)
            """, {"uid": s["uid"], "title": s.get("title", ""), "sub_uid": s.get("subject_uid")})
        stats["sections"] = len(sections)

        subsections = load_jsonl(os.path.join(KB_ROOT, "subsections.jsonl"))
        for ss in subsections:
            repo.write("""
                MERGE (subsec:Subsection {uid: $uid})
                SET subsec.title = $title
                WITH subsec
                MATCH (sec:Section {uid: $sec_uid})
                MERGE (sec)-[:HAS_SUBSECTION]->(subsec)
            """, {"uid": ss["uid"], "title": ss.get("title", ""), "sec_uid": ss.get("section_uid")})
        stats["subsections"] = len(subsections)

        # 2. Topics
        topics = load_jsonl(os.path.join(KB_ROOT, "topics.jsonl"))
        logger.info(f"Syncing {len(topics)} topics...")
        for t in topics:
            repo.write("""
                MERGE (top:Topic {uid: $uid})
                SET top.title = $title, 
                    top.description = $desc,
                    top.user_class_min = $min_c,
                    top.user_class_max = $max_c,
                    top.difficulty = $diff
                WITH top
                MATCH (subsec:Subsection {uid: $subsec_uid})
                MERGE (subsec)-[:HAS_TOPIC]->(top)
            """, {
                "uid": t["uid"],
                "title": t.get("title", ""),
                "desc": t.get("description", ""),
                "min_c": t.get("user_class_min"),
                "max_c": t.get("user_class_max"),
                "diff": t.get("difficulty_band"),
                "subsec_uid": t.get("section_uid") # In topics.jsonl it is often section_uid but refers to subsection or section
            })
        stats["topics"] = len(topics)

        # 3. Skills
        skills = load_jsonl(os.path.join(KB_ROOT, "skills.jsonl"))
        logger.info(f"Syncing {len(skills)} skills...")
        for s in skills:
            repo.write("""
                MERGE (sk:Skill {uid: $uid})
                SET sk.title = $title, 
                    sk.definition = $defn
                WITH sk
                MATCH (sub:Subject {uid: $sub_uid})
                MERGE (sub)-[:HAS_SKILL]->(sk)
            """, {
                "uid": s["uid"],
                "title": s.get("title", ""),
                "defn": s.get("definition", ""),
                "sub_uid": s.get("subject_uid", "MATH-FULL-V1")
            })
        stats["skills"] = len(skills)

        # 4. Methods
        methods = load_jsonl(os.path.join(KB_ROOT, "methods.jsonl"))
        logger.info(f"Syncing {len(methods)} methods...")
        for m in methods:
            repo.write("""
                MERGE (met:Method {uid: $uid})
                SET met.title = $title, 
                    met.content = $text
            """, {
                "uid": m["uid"],
                "title": m.get("title", ""),
                "text": m.get("method_text", "")
            })
        stats["methods"] = len(methods)

        # 5. Topic Skills
        topic_skills = load_jsonl(os.path.join(KB_ROOT, "topic_skills.jsonl"))
        logger.info(f"Syncing {len(topic_skills)} topic_skills...")
        for ts in topic_skills:
            repo.write("""
                MATCH (t:Topic {uid: $t_uid})
                MATCH (s:Skill {uid: $s_uid})
                MERGE (t)-[r:REQUIRES_SKILL]->(s)
                SET r.confidence = $conf,
                    r.weight = $weight
            """, {
                "t_uid": ts["topic_uid"],
                "s_uid": ts["skill_uid"],
                "conf": ts.get("confidence", 1.0),
                "weight": ts.get("weight", "primary")
            })
        stats["topic_skills"] = len(topic_skills)

        # 6. Skill Methods
        skill_methods = load_jsonl(os.path.join(KB_ROOT, "skill_methods.jsonl"))
        logger.info(f"Syncing {len(skill_methods)} skill_methods...")
        for sm in skill_methods:
            repo.write("""
                MATCH (s:Skill {uid: $s_uid})
                MATCH (m:Method {uid: $m_uid})
                MERGE (s)-[r:HAS_METHOD]->(m)
                SET r.confidence = $conf,
                    r.weight = $weight
            """, {
                "s_uid": sm["skill_uid"],
                "m_uid": sm["method_uid"],
                "conf": sm.get("confidence", 0.9),
                "weight": sm.get("weight", "linked")
            })
        stats["skill_methods"] = len(skill_methods)

        # 7. Topic Prereqs
        prereqs = load_jsonl(os.path.join(KB_ROOT, "topic_prereqs.jsonl"))
        logger.info(f"Syncing {len(prereqs)} prereqs...")
        for p in prereqs:
            repo.write("""
                MATCH (t:Topic {uid: $uid})
                MATCH (pre:Topic {uid: $pre_uid})
                MERGE (t)-[:PREREQ]->(pre)
            """, {
                "uid": p["target_uid"],
                "pre_uid": p["prereq_uid"]
            })
        stats["topic_prereqs"] = len(prereqs)

        return {"ok": True, "stats": stats}

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        repo.close()
