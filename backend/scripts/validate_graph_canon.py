#!/usr/bin/env python3
import sys
from typing import Dict, List, Tuple
from neo4j import GraphDatabase
import os
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

ALLOWED_LABELS = {"Subject","Section","Subsection","Topic","Skill","Method","Error","Example","Concept","Formula","TaskType","ContentUnit","Goal","Objective"}
ALLOWED_RELS = {"CONTAINS","PREREQ","USES_SKILL","LINKED","HAS_ERROR","HAS_EXAMPLE","HAS_CONCEPT","HAS_FORMULA","HAS_TASK_TYPE","HAS_UNIT","TARGETS","MEASURES"}

def fail(msg: str) -> None:
    print(msg)
    sys.exit(1)

def main():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        fail("Neo4j is not configured via env")
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    ok = True
    summary: Dict[str, int | List | Dict] = {}
    with drv.session() as s:
        # Check labels
        labs = s.run("CALL db.labels() YIELD label RETURN collect(label) AS labels").single()["labels"]
        disallowed = [l for l in labs if l not in ALLOWED_LABELS]
        summary["disallowed_labels"] = disallowed
        if disallowed: ok = False
        # Check relationship types
        rels = s.run("CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS rels").single()["rels"]
        bad_rels = [r for r in rels if r not in ALLOWED_RELS]
        summary["disallowed_relationships"] = bad_rels
        if bad_rels: ok = False
        # No PREREQ cycles
        rows = s.run("MATCH (a:Topic)-[:PREREQ]->(b:Topic) RETURN a.uid AS au, b.uid AS bu").data()
        g: Dict[str, List[str]] = {}
        for r in rows:
            g.setdefault(r["au"], []).append(r["bu"])
        cyc: List[List[str]] = []
        def dfs(node: str, stack: List[str], seen: set[Tuple[str,str]]):
            for nb in g.get(node, []):
                key = (node, nb)
                if key in seen: continue
                seen.add(key)
                if nb in stack:
                    i = stack.index(nb)
                    cyc.append(stack[i:] + [nb])
                else:
                    dfs(nb, stack + [nb], seen)
        for n in list(g.keys()):
            dfs(n, [n], set())
        summary["prereq_cycles"] = cyc
        if cyc: ok = False
        # Topic anchors: >=1 Skill AND (>=1 Example OR >=1 ContentUnit)
        missing_anchors: List[str] = []
        rs = s.run(
            """
            MATCH (t:Topic)
            OPTIONAL MATCH (t)-[:USES_SKILL]->(sk:Skill)
            OPTIONAL MATCH (t)-[:HAS_EXAMPLE]->(ex:Example)
            OPTIONAL MATCH (t)-[:HAS_UNIT]->(cu:ContentUnit)
            RETURN t.uid AS uid, COUNT(DISTINCT sk) AS skc, COUNT(DISTINCT ex) AS exc, COUNT(DISTINCT cu) AS cuc
            """
        ).data()
        for r in rs:
            if int(r["skc"]) < 1 or (int(r["exc"]) + int(r["cuc"])) < 1:
                missing_anchors.append(r["uid"])
        summary["topics_missing_anchors"] = missing_anchors
        if missing_anchors: ok = False
        # Hierarchy linking
        bad_hierarchy: List[str] = []
        rs = s.run(
            """
            MATCH (t:Topic)
            WHERE NOT EXISTS { (:Subsection)-[:CONTAINS]->(t) }
            RETURN t.uid AS uid
            """
        ).data()
        bad_hierarchy += [r["uid"] for r in rs]
        rs2 = s.run(
            """
            MATCH (t:Topic)<-[:CONTAINS]-(:Subsection)<-[:CONTAINS]-(sec:Section)
            WHERE NOT EXISTS { (:Subject)-[:CONTAINS]->(sec) }
            RETURN t.uid AS uid
            """
        ).data()
        bad_hierarchy += [r["uid"] for r in rs2]
        summary["topics_bad_hierarchy"] = bad_hierarchy
        if bad_hierarchy: ok = False
        # Orphans
        def count_orphans(cy: str) -> int:
            return int(s.run(cy).single()["c"])
        summary["orphan_skills"] = count_orphans("MATCH (sk:Skill) WHERE NOT EXISTS { (:Topic)-[:USES_SKILL]->(sk) } RETURN COUNT(sk) AS c")
        summary["orphan_methods"] = count_orphans("MATCH (m:Method) WHERE NOT EXISTS { (:Skill)-[:LINKED]->(m) } RETURN COUNT(m) AS c")
        summary["orphan_examples"] = count_orphans("MATCH (ex:Example) WHERE NOT EXISTS { (:Topic)-[:HAS_EXAMPLE]->(ex) } RETURN COUNT(ex) AS c")
        summary["orphan_errors"] = count_orphans("MATCH (e:Error) WHERE NOT EXISTS { (:Topic)-[:HAS_ERROR]->(e) } RETURN COUNT(e) AS c")
        summary["orphan_concepts"] = count_orphans("MATCH (c:Concept) WHERE NOT EXISTS { (:Topic)-[:HAS_CONCEPT]->(c) } RETURN COUNT(c) AS c")
        summary["orphan_formulas"] = count_orphans("MATCH (f:Formula) WHERE NOT EXISTS { (:Topic)-[:HAS_FORMULA]->(f) } RETURN COUNT(f) AS c")
        summary["orphan_task_types"] = count_orphans("MATCH (tt:TaskType) WHERE NOT EXISTS { (:Topic)-[:HAS_TASK_TYPE]->(tt) } RETURN COUNT(tt) AS c")
    drv.close()
    import json
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
