#!/usr/bin/env python3
import sys
from typing import Dict, List
from neo4j import GraphDatabase
import os
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

ALLOWED_LABELS = {"Subject","Section","Subsection","Topic","Skill","Method","Error","Example","Concept","Formula","TaskType","ContentUnit","Goal","Objective"}
ALLOWED_RELS = {"CONTAINS","PREREQ","USES_SKILL","LINKED","HAS_ERROR","HAS_EXAMPLE","HAS_CONCEPT","HAS_FORMULA","HAS_TASK_TYPE","HAS_UNIT","TARGETS","MEASURES"}

def run(session, cy: str, params: Dict | None = None) -> None:
    session.run(cy, params or {})

def migrate_relationships(session) -> Dict[str,int]:
    stats: Dict[str,int] = {}
    def exec_count(cy: str, key: str):
        res = session.run(cy).consume()
        stats[key] = res.counters.properties_set + res.counters.relationships_created + res.counters.relationships_deleted + res.counters.nodes_created + res.counters.nodes_deleted
    # HAS_SECTION -> CONTAINS
    exec_count("MATCH (a:Subject)-[r:HAS_SECTION]->(b:Section) MERGE (a)-[:CONTAINS]->(b) DELETE r", "HAS_SECTION_to_CONTAINS")
    # HAS_TOPIC -> CONTAINS
    exec_count("MATCH (a:Section)-[r:HAS_TOPIC]->(b:Topic) MERGE (a)-[:CONTAINS]->(b) DELETE r", "HAS_TOPIC_to_CONTAINS")
    # REQUIRES_SKILL -> USES_SKILL
    exec_count("MATCH (t:Topic)-[r:REQUIRES_SKILL]->(s:Skill) MERGE (t)-[nr:USES_SKILL]->(s) SET nr.weight=COALESCE(r.weight,1.0), nr.confidence=COALESCE(r.confidence,0.9) DELETE r", "REQUIRES_SKILL_to_USES_SKILL")
    # HAS_METHOD -> LINKED
    exec_count("MATCH (sk:Skill)-[r:HAS_METHOD]->(m:Method) MERGE (sk)-[nr:LINKED]->(m) SET nr.weight=COALESCE(r.weight,'linked'), nr.confidence=COALESCE(r.confidence,0.9) DELETE r", "HAS_METHOD_to_LINKED")
    # Remove Subject->HAS_SKILL per canon
    exec_count("MATCH (:Subject)-[r:HAS_SKILL]->(:Skill) DELETE r", "HAS_SKILL_removed")
    # HAS_THEORY (legacy) -> HAS_UNIT as ContentUnit with type='theory'
    exec_count(
        """
        MATCH (t)-[r:HAS_THEORY]->(th:Theory)
        MERGE (cu:ContentUnit {uid: 'CU-'+th.uid}) SET cu.type='theory', cu.payload=th.content
        MERGE (t)-[:HAS_UNIT]->(cu)
        DELETE r
        """,
        "HAS_THEORY_to_HAS_UNIT",
    )
    # HAS_EXAMPLE from Skill/Subject -> Topic/ContentUnit anchor
    exec_count(
        """
        MATCH (sk:Skill)-[r:HAS_EXAMPLE]->(ex:Example)
        WITH sk, ex, r
        OPTIONAL MATCH (t:Topic)-[:USES_SKILL]->(sk)
        FOREACH (_ IN CASE WHEN t IS NULL THEN [] ELSE [1] END | MERGE (t)-[:HAS_EXAMPLE]->(ex))
        DELETE r
        """,
        "Skill_HAS_EXAMPLE_moved",
    )
    exec_count(
        """
        MATCH (sub:Subject)-[r:HAS_EXAMPLE]->(ex:Example)
        DELETE r
        """,
        "Subject_HAS_EXAMPLE_deleted",
    )
    # HAS_LEARNING_PATH/HAS_PRACTICE_PATH/HAS_MASTERY_PATH -> HAS_UNIT
    exec_count("MATCH (t:Topic)-[r:HAS_LEARNING_PATH]->(u:ContentUnit) MERGE (t)-[:HAS_UNIT]->(u) DELETE r", "HAS_LEARNING_PATH_to_HAS_UNIT")
    exec_count("MATCH (t:Topic)-[r:HAS_PRACTICE_PATH]->(u:ContentUnit) MERGE (t)-[:HAS_UNIT]->(u) DELETE r", "HAS_PRACTICE_PATH_to_HAS_UNIT")
    exec_count("MATCH (t:Topic)-[r:HAS_MASTERY_PATH]->(u:ContentUnit) MERGE (t)-[:HAS_UNIT]->(u) DELETE r", "HAS_MASTERY_PATH_to_HAS_UNIT")
    # HAS_QUESTION -> HAS_EXAMPLE (map Question to Example)
    exec_count(
        """
        MATCH (t:Topic)-[r:HAS_QUESTION]->(q:Question)
        MERGE (ex:Example {uid:'EX-'+q.uid}) SET ex.title=COALESCE(q.title,q.uid), ex.statement=COALESCE(q.statement,''), ex.difficulty_level=COALESCE(q.difficulty,'medium')
        MERGE (t)-[:HAS_EXAMPLE]->(ex)
        DELETE r
        """,
        "HAS_QUESTION_to_HAS_EXAMPLE",
    )
    # TARGETS direction: Topic->Goal => Goal->TARGETS->Topic
    exec_count(
        """
        MATCH (t:Topic)-[r:TARGETS]->(g:Goal)
        MERGE (g)-[:TARGETS]->(t)
        DELETE r
        """,
        "TARGETS_reverse_goal",
    )
    # Topic->Objective via TARGETS: convert to Objective->MEASURES->Skill
    exec_count(
        """
        MATCH (t:Topic)-[r:TARGETS]->(o:Objective)
        WITH t, o, r
        MATCH (t)-[:USES_SKILL]->(sk:Skill)
        MERGE (o)-[:MEASURES]->(sk)
        DELETE r
        """,
        "Topic_TARGETS_Objective_to_MEASURES",
    )
    # Remove EVIDENCED_BY & SourceChunk (non-canonical)
    exec_count("MATCH ()-[r:EVIDENCED_BY]->(:SourceChunk) DELETE r", "EVIDENCED_BY_removed")
    exec_count("MATCH (sc:SourceChunk) DETACH DELETE sc", "SourceChunk_removed")
    # Ensure minimal content anchor for topics without Example or ContentUnit
    exec_count(
        """
        MATCH (t:Topic)
        WHERE NOT EXISTS { (t)-[:HAS_EXAMPLE]->() } AND NOT EXISTS { (t)-[:HAS_UNIT]->() }
        MERGE (cu:ContentUnit {uid:'CU-PL-'+t.uid})
        SET cu.type=COALESCE(cu.type,'placeholder'), cu.payload=COALESCE(cu.payload,'{}')
        MERGE (t)-[:HAS_UNIT]->(cu)
        """,
        "ContentUnit_placeholders_created",
    )
    return stats

def ensure_hierarchy(session) -> Dict[str,int]:
    stats: Dict[str,int] = {}
    # Ensure Section->Subsection->Topic; move Section->Topic under default Subsection
    res = session.run("MATCH (sec:Section)-[:CONTAINS]->(t:Topic) RETURN DISTINCT sec.uid AS su").data()
    moved = 0
    for row in res:
        su = row["su"]
        session.run("MERGE (sub:Subsection {uid:$uid}) SET sub.title=$title", {"uid": f"SUB-{su}-DEFAULT", "title": "Default"})
        session.run("MATCH (sec:Section {uid:$su}), (sub:Subsection {uid:$uid}) MERGE (sec)-[:CONTAINS]->(sub)", {"su": su, "uid": f"SUB-{su}-DEFAULT"})
        session.run(
            """
            MATCH (sec:Section {uid:$su})-[:CONTAINS]->(t:Topic)
            MATCH (sub:Subsection {uid:$uid})
            MERGE (sub)-[:CONTAINS]->(t)
            WITH sec, t
            MATCH (sec)-[rt:CONTAINS]->(t)
            DELETE rt
            """,
            {"su": su, "uid": f"SUB-{su}-DEFAULT"},
        )
        moved += 1
    stats["topics_moved_under_subsection"] = moved
    # Ensure each Topic has a Subsection parent
    session.run(
        """
        MATCH (t:Topic)
        WHERE NOT EXISTS { (:Subsection)-[:CONTAINS]->(t) }
        MATCH (sec:Section)-[:CONTAINS]->(t)
        MERGE (sub:Subsection {uid:'SUB-'+sec.uid+'-DEFAULT'}) SET sub.title='Default'
        MERGE (sec)-[:CONTAINS]->(sub)
        MERGE (sub)-[:CONTAINS]->(t)
        """
    )  # idempotent
    return stats

def remove_orphans(session) -> Dict[str,List[str]]:
    report: Dict[str,List[str]] = {}
    def list_uids(cy: str, key: str):
        report[key] = [r["uid"] for r in session.run(cy)]
    list_uids("MATCH (t:Topic) WHERE NOT EXISTS { (:Subsection)-[:CONTAINS]->(t) } RETURN t.uid AS uid", "orphan_topics")
    list_uids("MATCH (sec:Section) WHERE NOT EXISTS { (:Subject)-[:CONTAINS]->(sec) } RETURN sec.uid AS uid", "orphan_sections")
    list_uids("MATCH (sk:Skill) WHERE NOT EXISTS { (:Topic)-[:USES_SKILL]->(sk) } RETURN sk.uid AS uid", "orphan_skills")
    list_uids("MATCH (m:Method) WHERE NOT EXISTS { (:Skill)-[:LINKED]->(m) } RETURN m.uid AS uid", "orphan_methods")
    list_uids("MATCH (ex:Example) WHERE NOT EXISTS { (:Topic)-[:HAS_EXAMPLE]->(ex) } RETURN ex.uid AS uid", "orphan_examples")
    list_uids("MATCH (cu:ContentUnit) WHERE NOT EXISTS { (:Topic)-[:HAS_UNIT]->(cu) } RETURN cu.uid AS uid", "orphan_units")
    list_uids("MATCH (c:Concept) WHERE NOT EXISTS { (:Topic)-[:HAS_CONCEPT]->(c) } RETURN c.uid AS uid", "orphan_concepts")
    list_uids("MATCH (e:Error) WHERE NOT EXISTS { (:Topic)-[:HAS_ERROR]->(e) } RETURN e.uid AS uid", "orphan_errors")
    list_uids("MATCH (f:Formula) WHERE NOT EXISTS { (:Topic)-[:HAS_FORMULA]->(f) } RETURN f.uid AS uid", "orphan_formulas")
    list_uids("MATCH (tt:TaskType) WHERE NOT EXISTS { (:Topic)-[:HAS_TASK_TYPE]->(tt) } RETURN tt.uid AS uid", "orphan_task_types")
    # Delete orphans
    for key, uids in report.items():
        if not uids: continue
        session.run(f"UNWIND $uids AS u MATCH (n) WHERE n.uid=u DETACH DELETE n", {"uids": uids})
    return report

def main():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        print("Neo4j is not configured via env", file=sys.stderr)
        sys.exit(1)
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with drv.session() as s:
        stats = {}
        stats.update(migrate_relationships(s))
        stats.update(ensure_hierarchy(s))
        orphans = remove_orphans(s)
    drv.close()
    print(json_dump({"stats": stats, "orphans_removed": {k: len(v) for k, v in orphans.items()}}))

def json_dump(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
