import os
import json
from typing import Dict, List
from neo4j import GraphDatabase
from app.config.settings import settings
from app.services.graph.neo4j_repo import Neo4jRepo, get_driver
from app.services.kb.jsonl_io import load_jsonl, get_path, get_path_in
from app.services.kb.jsonl_io import normalize_skill_topics_to_topic_skills

def compute_user_weight(base_weight: float, score: float) -> float:
    delta = (50.0 - float(score)) / 100.0
    new_weight = max(0.0, min(1.0, float(base_weight) + delta))
    return new_weight

def compute_topic_user_weight(topic_uid: str, score: float, base_weight: float | None = None) -> Dict:
    if base_weight is None:
        if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password.get_secret_value()):
            base_weight = 0.5
        else:
            try:
                repo = Neo4jRepo()
                rows = repo.read("MATCH (t:Topic {uid:$uid}) RETURN coalesce(t.dynamic_weight, t.static_weight, 0.5) AS w", {"uid": topic_uid})
                base_weight = rows[0]["w"] if rows else 0.5
                repo.close()
            except Exception:
                base_weight = 0.5
    return {"topic_uid": topic_uid, "base_weight": base_weight, "user_weight": compute_user_weight(base_weight, score)}

def compute_skill_user_weight(skill_uid: str, score: float, base_weight: float | None = None) -> Dict:
    if base_weight is None:
        if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password.get_secret_value()):
            base_weight = 0.5
        else:
            try:
                repo = Neo4jRepo()
                rows = repo.read("MATCH (s:Skill {uid:$uid}) RETURN coalesce(s.dynamic_weight, s.static_weight, 0.5) AS w", {"uid": skill_uid})
                base_weight = rows[0]["w"] if rows else 0.5
                repo.close()
            except Exception:
                base_weight = 0.5
    return {"skill_uid": skill_uid, "base_weight": base_weight, "user_weight": compute_user_weight(base_weight, score)}

def knowledge_level_from_weight(weight: float) -> str:
    w = float(weight)
    if w < 0.3:
        return "low"
    if w < 0.7:
        return "medium"
    return "high"

def ensure_constraints(session):
    session.run("CREATE CONSTRAINT subject_uid_unique IF NOT EXISTS FOR (n:Subject) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT section_uid_unique IF NOT EXISTS FOR (n:Section) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT topic_uid_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT skill_uid_unique IF NOT EXISTS FOR (n:Skill) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT method_uid_unique IF NOT EXISTS FOR (n:Method) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT example_uid_unique IF NOT EXISTS FOR (n:Example) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT error_uid_unique IF NOT EXISTS FOR (n:Error) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT contentunit_uid_unique IF NOT EXISTS FOR (n:ContentUnit) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT goal_uid_unique IF NOT EXISTS FOR (n:Goal) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT objective_uid_unique IF NOT EXISTS FOR (n:Objective) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE INDEX subject_title_idx IF NOT EXISTS FOR (n:Subject) ON (n.title)")
    session.run("CREATE INDEX section_title_idx IF NOT EXISTS FOR (n:Section) ON (n.title)")
    session.run("CREATE INDEX topic_title_idx IF NOT EXISTS FOR (n:Topic) ON (n.title)")
    session.run("CREATE INDEX skill_title_idx IF NOT EXISTS FOR (n:Skill) ON (n.title)")
    session.run("CREATE INDEX method_title_idx IF NOT EXISTS FOR (n:Method) ON (n.title)")
    session.run("CREATE CONSTRAINT section_title_scope_unique IF NOT EXISTS FOR (n:Section) REQUIRE (n.subject_uid, n.title) IS UNIQUE")
    session.run("CREATE CONSTRAINT topic_title_scope_unique IF NOT EXISTS FOR (n:Topic) REQUIRE (n.section_uid, n.title) IS UNIQUE")
    session.run("CREATE CONSTRAINT skill_title_scope_unique IF NOT EXISTS FOR (n:Skill) REQUIRE (n.subject_uid, n.title) IS UNIQUE")
    session.run("CREATE INDEX example_title_idx IF NOT EXISTS FOR (n:Example) ON (n.title)")
    session.run("CREATE INDEX example_difficulty_idx IF NOT EXISTS FOR (n:Example) ON (n.difficulty)")

def ensure_weight_defaults(session):
    session.run("MATCH (t:Topic) WHERE t.static_weight IS NULL SET t.static_weight = 0.5")
    session.run("MATCH (t:Topic) WHERE t.dynamic_weight IS NULL SET t.dynamic_weight = t.static_weight")
    session.run("MATCH (s:Skill) WHERE s.static_weight IS NULL SET s.static_weight = 0.5")
    session.run("MATCH (s:Skill) WHERE s.dynamic_weight IS NULL SET s.dynamic_weight = s.static_weight")

def ensure_weight_defaults_repo(repo: Neo4jRepo):
    repo.write("MATCH (t:Topic) WHERE t.static_weight IS NULL SET t.static_weight = 0.5")
    repo.write("MATCH (t:Topic) WHERE t.dynamic_weight IS NULL SET t.dynamic_weight = t.static_weight")
    repo.write("MATCH (s:Skill) WHERE s.static_weight IS NULL SET s.static_weight = 0.5")
    repo.write("MATCH (s:Skill) WHERE s.dynamic_weight IS NULL SET s.dynamic_weight = s.static_weight")


def sync_from_jsonl() -> Dict:
    subjects = load_jsonl(get_path('subjects.jsonl'))
    sections = load_jsonl(get_path('sections.jsonl'))
    subsections = load_jsonl(get_path('subsections.jsonl'))
    topics = load_jsonl(get_path('topics.jsonl'))
    skills = load_jsonl(get_path('skills.jsonl'))
    methods = load_jsonl(get_path('methods.jsonl'))
    skill_methods = load_jsonl(get_path('skill_methods.jsonl'))
    normalize_skill_topics_to_topic_skills()
    topic_skills = load_jsonl(get_path('topic_skills.jsonl'))
    topic_goals = load_jsonl(get_path('topic_goals.jsonl'))
    topic_objectives = load_jsonl(get_path('topic_objectives.jsonl'))
    topic_prereqs = load_jsonl(get_path('topic_prereqs.jsonl'))
    content_units = load_jsonl(get_path('content_units.jsonl'))
    examples = load_jsonl(get_path('examples.jsonl'))
    example_skills = load_jsonl(get_path('example_skills.jsonl'))
    from app.schemas.proposal import Operation, OpType
    from app.services.proposal_service import create_draft_proposal
    from app.db.pg import ensure_tables, get_conn
    ops: list[Operation] = []
    for s in subjects:
        ops.append(Operation(op_id="N-"+(s.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=s.get("uid"), properties_delta={"type":"Subject","uid":s.get("uid"),"title":s.get("title"),"description":s.get("description")}))
    for sec in sections:
        ops.append(Operation(op_id="N-"+(sec.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sec.get("uid"), properties_delta={"type":"Section","uid":sec.get("uid"),"title":sec.get("title"),"description":sec.get("description")}))
    for sub in subsections:
        ops.append(Operation(op_id="N-"+(sub.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sub.get("uid"), properties_delta={"type":"Subsection","uid":sub.get("uid"),"title":sub.get("title"),"description":sub.get("description")}))
    for t in topics:
        ops.append(Operation(op_id="N-"+(t.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=t.get("uid"), properties_delta={"type":"Topic","uid":t.get("uid"),"title":t.get("title"),"description":t.get("description"),"user_class_min":t.get("user_class_min"),"user_class_max":t.get("user_class_max"),"difficulty_band":t.get("difficulty_band")}))
    for sk in skills:
        ops.append(Operation(op_id="N-"+(sk.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sk.get("uid"), properties_delta={"type":"Skill","uid":sk.get("uid"),"title":sk.get("title"),"definition":sk.get("definition"),"applicability_types":sk.get("applicability_types")}))
    for m in methods:
        ops.append(Operation(op_id="N-"+(m.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=m.get("uid"), properties_delta={"type":"Method","uid":m.get("uid"),"title":m.get("title"),"method_text":m.get("method_text"),"applicability_types":m.get("applicability_types")}))
    unit_rows = [{"uid": (u.get("uid") or f"UNIT-{u.get('topic_uid')}-{abs(hash((u.get('type') or '')+(u.get('branch') or '')))%100000}"), "topic_uid": u.get("topic_uid"), "type": u.get("type"), "payload": __import__('json').dumps(u.get("payload", {}), ensure_ascii=False), "complexity": float(u.get("complexity", 0.0) or 0.0)} for u in content_units if u.get("topic_uid")]
    for u in unit_rows:
        ops.append(Operation(op_id="N-"+(u.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=u.get("uid"), properties_delta={"type":"ContentUnit","uid":u.get("uid"),"type":u.get("type"),"payload":u.get("payload"),"complexity":u.get("complexity")}))
    for sec in [s for s in sections if s.get("subject_uid")]:
        ops.append(Operation(op_id="E-"+(sec.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(sec.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sec.get("subject_uid"),"to_uid":sec.get("uid")}))
    for sub in [ss for ss in subsections if ss.get("section_uid")]:
        ops.append(Operation(op_id="E-"+(sub.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(sub.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sub.get("section_uid"),"to_uid":sub.get("uid")}))
    for t in [x for x in topics if x.get("section_uid")]:
        ops.append(Operation(op_id="E-"+(t.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(t.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":t.get("section_uid"),"to_uid":t.get("uid")}))
    for ts in [x for x in topic_skills if x.get("topic_uid") and x.get("skill_uid")]:
        ops.append(Operation(op_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), properties_delta={"type":"USES_SKILL","from_uid":ts.get("topic_uid"),"to_uid":ts.get("skill_uid"),"weight":ts.get("weight","linked"),"confidence":ts.get("confidence",0.9)}))
    for pr in topic_prereqs:
        tu = pr.get('topic_uid') or pr.get('target_uid')
        pu = pr.get('prereq_uid')
        if tu and pu:
            ops.append(Operation(op_id="E-"+tu+"-"+pu, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+pu, properties_delta={"type":"PREREQ","from_uid":tu,"to_uid":pu,"weight":pr.get("weight",1.0),"confidence":pr.get("confidence",0.9)}))
    for u in unit_rows:
        ops.append(Operation(op_id="E-"+(u.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(u.get("uid") or ""), properties_delta={"type":"HAS_UNIT","from_uid":u.get("topic_uid"),"to_uid":u.get("uid")}))
    for ex in [e for e in examples if e.get("uid")]:
        ex_uid = ex.get("uid")
        ops.append(Operation(op_id="N-"+ex_uid, op_type=OpType.MERGE_NODE, target_id=ex_uid, properties_delta={"type":"Example","uid":ex_uid,"title":ex.get("title"),"statement":ex.get("statement"),"difficulty_level":ex.get("difficulty")}))
        tu = ex.get("topic_uid")
        if tu:
            ops.append(Operation(op_id="E-"+tu+"-"+ex_uid, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+ex_uid, properties_delta={"type":"HAS_EXAMPLE","from_uid":tu,"to_uid":ex_uid}))
    for es in [x for x in example_skills if x.get("example_uid") and x.get("skill_uid")]:
        ops.append(Operation(op_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), properties_delta={"type":"LINKED","from_uid":es.get("example_uid"),"to_uid":es.get("skill_uid"),"role":es.get("role","target")}))
    for sm in [x for x in skill_methods if x.get("skill_uid") and x.get("method_uid")]:
        ops.append(Operation(op_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"LINKED","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"weight":sm.get("weight","linked"),"confidence":sm.get("confidence",0.9)}))
        ops.append(Operation(op_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"BASED_ON","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"confidence":sm.get("confidence",0.9)}))
    goals_rows = [{"uid": g.get('uid') or f"GOAL-{g.get('topic_uid')}-{abs(hash(g.get('title','')))%100000}", "title": g.get('title'), "topic_uid": g.get('topic_uid')} for g in topic_goals]
    for g in goals_rows:
        ops.append(Operation(op_id="N-"+(g.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=g.get("uid"), properties_delta={"type":"Goal","uid":g.get("uid"),"title":g.get("title")}))
        if g.get("topic_uid"):
            ops.append(Operation(op_id="E-"+(g.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(g.get("uid") or ""), properties_delta={"type":"TARGETS","from_uid":g.get("uid"),"to_uid":g.get("topic_uid")}))
    objs_rows = [{"uid": o.get('uid') or f"OBJ-{o.get('topic_uid')}-{abs(hash(o.get('title','')))%100000}", "title": o.get('title'), "topic_uid": o.get('topic_uid')} for o in topic_objectives]
    for o in objs_rows:
        ops.append(Operation(op_id="N-"+(o.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=o.get("uid"), properties_delta={"type":"Objective","uid":o.get("uid"),"title":o.get("title")}))
        t_uid = o.get("topic_uid")
        if t_uid:
            for ts in [x for x in topic_skills if x.get("topic_uid")==t_uid]:
                ops.append(Operation(op_id="E-"+(o.get("uid") or "")+"-"+(ts.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(o.get("uid") or "")+"-"+(ts.get("skill_uid") or ""), properties_delta={"type":"MEASURES","from_uid":o.get("uid"),"to_uid":ts.get("skill_uid")}))
    ensure_tables()
    p = create_draft_proposal("public", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        from json import dumps
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, "DRAFT", dumps([o.model_dump() for o in ops])))
    conn.close()
    from app.workers.commit import commit_proposal
    res = commit_proposal(p.proposal_id)
    return {"ok": bool(res.get("ok")), "proposal_id": p.proposal_id, "ops": len(ops), "commit_result": res}

def sync_from_jsonl_dir(base_dir: str) -> Dict:
    subjects = load_jsonl(get_path_in(base_dir, 'subjects.jsonl'))
    sections = load_jsonl(get_path_in(base_dir, 'sections.jsonl'))
    subsections = load_jsonl(get_path_in(base_dir, 'subsections.jsonl'))
    topics = load_jsonl(get_path_in(base_dir, 'topics.jsonl'))
    skills_all = load_jsonl(get_path_in(base_dir, 'skills.jsonl'))
    methods_all = load_jsonl(get_path_in(base_dir, 'methods.jsonl'))
    skill_methods_all = load_jsonl(get_path_in(base_dir, 'skill_methods.jsonl'))
    normalize_skill_topics_to_topic_skills()
    topic_skills = load_jsonl(get_path_in(base_dir, 'topic_skills.jsonl'))
    topic_goals = load_jsonl(get_path_in(base_dir, 'topic_goals.jsonl'))
    topic_objectives = load_jsonl(get_path_in(base_dir, 'topic_objectives.jsonl'))
    topic_prereqs = load_jsonl(get_path_in(base_dir, 'topic_prereqs.jsonl'))
    content_units = load_jsonl(get_path_in(base_dir, 'content_units.jsonl'))
    examples = load_jsonl(get_path_in(base_dir, 'examples.jsonl'))
    example_skills = load_jsonl(get_path_in(base_dir, 'example_skills.jsonl'))
    from app.schemas.proposal import Operation, OpType
    from app.services.proposal_service import create_draft_proposal
    from app.db.pg import ensure_tables, get_conn
    ops: list[Operation] = []
    for s in subjects:
        ops.append(Operation(op_id="N-"+(s.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=s.get("uid"), properties_delta={"type":"Subject","uid":s.get("uid"),"title":s.get("title"),"description":s.get("description")}))
    for sec in sections:
        ops.append(Operation(op_id="N-"+(sec.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sec.get("uid"), properties_delta={"type":"Section","uid":sec.get("uid"),"title":sec.get("title"),"description":sec.get("description")}))
    for sub in subsections:
        ops.append(Operation(op_id="N-"+(sub.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sub.get("uid"), properties_delta={"type":"Subsection","uid":sub.get("uid"),"title":sub.get("title"),"description":sub.get("description")}))
    for t in topics:
        ops.append(Operation(op_id="N-"+(t.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=t.get("uid"), properties_delta={"type":"Topic","uid":t.get("uid"),"title":t.get("title"),"description":t.get("description")}))
    for sk in skills:
        ops.append(Operation(op_id="N-"+(sk.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sk.get("uid"), properties_delta={"type":"Skill","uid":sk.get("uid"),"title":sk.get("title"),"definition":sk.get("definition"),"applicability_types":sk.get("applicability_types")}))
    for m in methods:
        ops.append(Operation(op_id="N-"+(m.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=m.get("uid"), properties_delta={"type":"Method","uid":m.get("uid"),"title":m.get("title"),"method_text":m.get("method_text"),"applicability_types":m.get("applicability_types")}))
    unit_rows = [{"uid": (u.get("uid") or f"UNIT-{u.get('topic_uid')}-{abs(hash((u.get('type') or '')+(u.get('branch') or '')))%100000}"), "topic_uid": u.get("topic_uid"), "type": u.get("type"), "payload": __import__('json').dumps(u.get("payload", {}), ensure_ascii=False), "complexity": float(u.get("complexity", 0.0) or 0.0)} for u in content_units if u.get("topic_uid")]
    for u in unit_rows:
        ops.append(Operation(op_id="N-"+(u.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=u.get("uid"), properties_delta={"type":"ContentUnit","uid":u.get("uid"),"type":u.get("type"),"payload":u.get("payload"),"complexity":u.get("complexity")}))
    for sec in [s for s in sections if s.get("subject_uid")]:
        ops.append(Operation(op_id="E-"+(sec.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(sec.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sec.get("subject_uid"),"to_uid":sec.get("uid")}))
    for sub in [ss for ss in subsections if ss.get("section_uid")]:
        ops.append(Operation(op_id="E-"+(sub.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(sub.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sub.get("section_uid"),"to_uid":sub.get("uid")}))
    for t in [x for x in topics if x.get("section_uid")]:
        ops.append(Operation(op_id="E-"+(t.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(t.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":t.get("section_uid"),"to_uid":t.get("uid")}))
    for ts in [x for x in topic_skills if x.get("topic_uid") and x.get("skill_uid")]:
        ops.append(Operation(op_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), properties_delta={"type":"USES_SKILL","from_uid":ts.get("topic_uid"),"to_uid":ts.get("skill_uid"),"weight":ts.get("weight","linked"),"confidence":ts.get("confidence",0.9)}))
    for pr in topic_prereqs:
        tu = pr.get('topic_uid') or pr.get('target_uid')
        pu = pr.get('prereq_uid')
        if tu and pu:
            ops.append(Operation(op_id="E-"+tu+"-"+pu, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+pu, properties_delta={"type":"PREREQ","from_uid":tu,"to_uid":pu,"weight":pr.get("weight",1.0),"confidence":pr.get("confidence",0.9)}))
    for u in unit_rows:
        ops.append(Operation(op_id="E-"+(u.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(u.get("uid") or ""), properties_delta={"type":"HAS_UNIT","from_uid":u.get("topic_uid"),"to_uid":u.get("uid")}))
    for ex in [e for e in examples if e.get("uid")]:
        ex_uid = ex.get("uid")
        ops.append(Operation(op_id="N-"+ex_uid, op_type=OpType.MERGE_NODE, target_id=ex_uid, properties_delta={"type":"Example","uid":ex_uid,"title":ex.get("title"),"statement":ex.get("statement"),"difficulty_level":ex.get("difficulty")}))
        tu = ex.get("topic_uid")
        if tu:
            ops.append(Operation(op_id="E-"+tu+"-"+ex_uid, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+ex_uid, properties_delta={"type":"HAS_EXAMPLE","from_uid":tu,"to_uid":ex_uid}))
    for es in [x for x in example_skills if x.get("example_uid") and x.get("skill_uid")]:
        ops.append(Operation(op_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), properties_delta={"type":"LINKED","from_uid":es.get("example_uid"),"to_uid":es.get("skill_uid"),"role":es.get("role","target")}))
    for sm in [x for x in skill_methods if x.get("skill_uid") and x.get("method_uid")]:
        ops.append(Operation(op_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"LINKED","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"weight":sm.get("weight","linked"),"confidence":sm.get("confidence",0.9)}))
        ops.append(Operation(op_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"BASED_ON","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"confidence":sm.get("confidence",0.9)}))
    ensure_tables()
    p = create_draft_proposal("public", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        from json import dumps
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, "DRAFT", dumps([o.model_dump() for o in ops])))
    conn.close()
    from app.workers.commit import commit_proposal
    res = commit_proposal(p.proposal_id)
    return {"ok": bool(res.get("ok")), "proposal_id": p.proposal_id, "ops": len(ops)}

def sync_from_jsonl_dir_sections(base_dir: str, section_uids: List[str]) -> Dict:
    subjects = load_jsonl(get_path_in(base_dir, 'subjects.jsonl'))
    sections = [s for s in load_jsonl(get_path_in(base_dir, 'sections.jsonl')) if s.get('uid') in set(section_uids)]
    subsections = [ss for ss in load_jsonl(get_path_in(base_dir, 'subsections.jsonl')) if ss.get('section_uid') in {s.get('uid') for s in sections}]
    topics = [t for t in load_jsonl(get_path_in(base_dir, 'topics.jsonl')) if t.get('section_uid') in {ss.get('uid') for ss in subsections}]
    skills = load_jsonl(get_path_in(base_dir, 'skills.jsonl'))
    methods = load_jsonl(get_path_in(base_dir, 'methods.jsonl'))
    skill_methods = load_jsonl(get_path_in(base_dir, 'skill_methods.jsonl'))
    normalize_skill_topics_to_topic_skills()
    topic_skills = [x for x in load_jsonl(get_path_in(base_dir, 'topic_skills.jsonl')) if x.get('topic_uid') in {t.get('uid') for t in topics}]
    skill_uids = {x.get('skill_uid') for x in topic_skills if x.get('skill_uid')}
    skills = [s for s in skills_all if s.get('uid') in skill_uids]
    skill_methods = [sm for sm in skill_methods_all if sm.get('skill_uid') in skill_uids]
    method_uids = {sm.get('method_uid') for sm in skill_methods if sm.get('method_uid')}
    methods = [m for m in methods_all if m.get('uid') in method_uids]
    topic_goals = [g for g in load_jsonl(get_path_in(base_dir, 'topic_goals.jsonl')) if g.get('topic_uid') in {t.get('uid') for t in topics}]
    topic_objectives = [o for o in load_jsonl(get_path_in(base_dir, 'topic_objectives.jsonl')) if o.get('topic_uid') in {t.get('uid') for t in topics}]
    topic_prereqs = [pr for pr in load_jsonl(get_path_in(base_dir, 'topic_prereqs.jsonl')) if (pr.get('target_uid') or pr.get('topic_uid')) in {t.get('uid') for t in topics}]
    content_units = load_jsonl(get_path_in(base_dir, 'content_units.jsonl'))
    examples = [e for e in load_jsonl(get_path_in(base_dir, 'examples.jsonl')) if e.get('topic_uid') in {t.get('uid') for t in topics}]
    example_skills = [es for es in load_jsonl(get_path_in(base_dir, 'example_skills.jsonl')) if es.get('example_uid') in {e.get('uid') for e in examples}]
    from app.schemas.proposal import Operation, OpType
    from app.services.proposal_service import create_draft_proposal
    from app.db.pg import ensure_tables, get_conn
    ops: list[Operation] = []
    for s in subjects:
        ops.append(Operation(op_id="N-"+(s.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=s.get("uid"), properties_delta={"type":"Subject","uid":s.get("uid"),"title":s.get("title"),"description":s.get("description")}))
    for sec in sections:
        ops.append(Operation(op_id="N-"+(sec.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sec.get("uid"), properties_delta={"type":"Section","uid":sec.get("uid"),"title":sec.get("title"),"description":sec.get("description")}))
    for sub in subsections:
        ops.append(Operation(op_id="N-"+(sub.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sub.get("uid"), properties_delta={"type":"Subsection","uid":sub.get("uid"),"title":sub.get("title"),"description":sub.get("description")}))
    for t in topics:
        ops.append(Operation(op_id="N-"+(t.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=t.get("uid"), properties_delta={"type":"Topic","uid":t.get("uid"),"title":t.get("title"),"description":t.get("description"),"user_class_min":t.get("user_class_min"),"user_class_max":t.get("user_class_max"),"difficulty_band":t.get("difficulty_band")}))
    for sk in skills:
        ops.append(Operation(op_id="N-"+(sk.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sk.get("uid"), properties_delta={"type":"Skill","uid":sk.get("uid"),"title":sk.get("title"),"definition":sk.get("definition"),"applicability_types":sk.get("applicability_types")}))
    for m in methods:
        ops.append(Operation(op_id="N-"+(m.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=m.get("uid"), properties_delta={"type":"Method","uid":m.get("uid"),"title":m.get("title"),"method_text":m.get("method_text"),"applicability_types":m.get("applicability_types")}))
    unit_rows = [{"uid": (u.get("uid") or f"UNIT-{u.get('topic_uid')}-{abs(hash((u.get('type') or '')+(u.get('branch') or '')))%100000}"), "topic_uid": u.get("topic_uid"), "type": u.get("type"), "payload": __import__('json').dumps(u.get("payload", {}), ensure_ascii=False), "complexity": float(u.get("complexity", 0.0) or 0.0)} for u in content_units if u.get("topic_uid") in {t.get("uid") for t in topics}]
    for u in unit_rows:
        ops.append(Operation(op_id="N-"+(u.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=u.get("uid"), properties_delta={"type":"ContentUnit","uid":u.get("uid"),"type":u.get("type"),"payload":u.get("payload"),"complexity":u.get("complexity")}))
    for sec in sections:
        ops.append(Operation(op_id="E-"+(sec.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(sec.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sec.get("subject_uid"),"to_uid":sec.get("uid")}))
    for sub in subsections:
        ops.append(Operation(op_id="E-"+(sub.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(sub.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sub.get("section_uid"),"to_uid":sub.get("uid")}))
    for t in topics:
        ops.append(Operation(op_id="E-"+(t.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(t.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":t.get("section_uid"),"to_uid":t.get("uid")}))
    for ts in topic_skills:
        ops.append(Operation(op_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), properties_delta={"type":"USES_SKILL","from_uid":ts.get("topic_uid"),"to_uid":ts.get("skill_uid"),"weight":ts.get("weight","linked"),"confidence":ts.get("confidence",0.9)}))
    for pr in topic_prereqs:
        tu = pr.get('topic_uid') or pr.get('target_uid')
        pu = pr.get('prereq_uid')
        if tu and pu:
            ops.append(Operation(op_id="E-"+tu+"-"+pu, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+pu, properties_delta={"type":"PREREQ","from_uid":tu,"to_uid":pu,"weight":pr.get("weight",1.0),"confidence":pr.get("confidence",0.9)}))
    for u in unit_rows:
        ops.append(Operation(op_id="E-"+(u.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(u.get("uid") or ""), properties_delta={"type":"HAS_UNIT","from_uid":u.get("topic_uid"),"to_uid":u.get("uid")}))
    for ex in examples:
        ex_uid = ex.get("uid")
        ops.append(Operation(op_id="N-"+ex_uid, op_type=OpType.MERGE_NODE, target_id=ex_uid, properties_delta={"type":"Example","uid":ex_uid,"title":ex.get("title"),"statement":ex.get("statement"),"difficulty_level":ex.get("difficulty")}))
        tu = ex.get("topic_uid")
        if tu:
            ops.append(Operation(op_id="E-"+tu+"-"+ex_uid, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+ex_uid, properties_delta={"type":"HAS_EXAMPLE","from_uid":tu,"to_uid":ex_uid}))
    for es in example_skills:
        ops.append(Operation(op_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), properties_delta={"type":"LINKED","from_uid":es.get("example_uid"),"to_uid":es.get("skill_uid"),"role":es.get("role","target")}))
    for sm in [x for x in skill_methods if x.get("skill_uid") and x.get("method_uid")]:
        ops.append(Operation(op_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"LINKED","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"weight":sm.get("weight","linked"),"confidence":sm.get("confidence",0.9)}))
        ops.append(Operation(op_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"BASED_ON","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"confidence":sm.get("confidence",0.9)}))
    ensure_tables()
    p = create_draft_proposal("public", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        from json import dumps
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, "DRAFT", dumps([o.model_dump() for o in ops])))
    conn.close()
    from app.workers.commit import commit_proposal
    res = commit_proposal(p.proposal_id)
    return {"ok": bool(res.get("ok")), "proposal_id": p.proposal_id, "ops": len(ops)}

def sync_from_jsonl_dir_subsections(base_dir: str, subsection_uids: List[str]) -> Dict:
    subjects = load_jsonl(get_path_in(base_dir, 'subjects.jsonl'))
    sections = load_jsonl(get_path_in(base_dir, 'sections.jsonl'))
    subsections_all = load_jsonl(get_path_in(base_dir, 'subsections.jsonl'))
    subsections = [ss for ss in subsections_all if ss.get('uid') in set(subsection_uids)]
    topics = [t for t in load_jsonl(get_path_in(base_dir, 'topics.jsonl')) if t.get('section_uid') in {ss.get('uid') for ss in subsections}]
    skills = load_jsonl(get_path_in(base_dir, 'skills.jsonl'))
    methods = load_jsonl(get_path_in(base_dir, 'methods.jsonl'))
    skill_methods = load_jsonl(get_path_in(base_dir, 'skill_methods.jsonl'))
    normalize_skill_topics_to_topic_skills()
    topic_skills = [x for x in load_jsonl(get_path_in(base_dir, 'topic_skills.jsonl')) if x.get('topic_uid') in {t.get('uid') for t in topics}]
    topic_goals = [g for g in load_jsonl(get_path_in(base_dir, 'topic_goals.jsonl')) if g.get('topic_uid') in {t.get('uid') for t in topics}]
    topic_objectives = [o for o in load_jsonl(get_path_in(base_dir, 'topic_objectives.jsonl')) if o.get('topic_uid') in {t.get('uid') for t in topics}]
    topic_prereqs = [pr for pr in load_jsonl(get_path_in(base_dir, 'topic_prereqs.jsonl')) if (pr.get('target_uid') or pr.get('topic_uid')) in {t.get('uid') for t in topics}]
    content_units = load_jsonl(get_path_in(base_dir, 'content_units.jsonl'))
    examples = [e for e in load_jsonl(get_path_in(base_dir, 'examples.jsonl')) if e.get('topic_uid') in {t.get('uid') for t in topics}]
    example_skills = [es for es in load_jsonl(get_path_in(base_dir, 'example_skills.jsonl')) if es.get('example_uid') in {e.get('uid') for e in examples}]
    from app.schemas.proposal import Operation, OpType
    from app.services.proposal_service import create_draft_proposal
    from app.db.pg import ensure_tables, get_conn
    ops: list[Operation] = []
    for s in subjects:
        ops.append(Operation(op_id="N-"+(s.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=s.get("uid"), properties_delta={"type":"Subject","uid":s.get("uid"),"title":s.get("title"),"description":s.get("description")}))
    for ss in subsections:
        sec_uid = ss.get("section_uid")
        sec = next((x for x in sections if x.get("uid")==sec_uid), None)
        if sec:
            ops.append(Operation(op_id="N-"+(sec.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sec.get("uid"), properties_delta={"type":"Section","uid":sec.get("uid"),"title":sec.get("title"),"description":sec.get("description")}))
        ops.append(Operation(op_id="N-"+(ss.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=ss.get("uid"), properties_delta={"type":"Subsection","uid":ss.get("uid"),"title":ss.get("title"),"description":ss.get("description")}))
        if sec:
            ops.append(Operation(op_id="E-"+(ss.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(ss.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":sec.get("uid"),"to_uid":ss.get("uid")}))
    for t in topics:
        ops.append(Operation(op_id="N-"+(t.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=t.get("uid"), properties_delta={"type":"Topic","uid":t.get("uid"),"title":t.get("title"),"description":t.get("description"),"user_class_min":t.get("user_class_min"),"user_class_max":t.get("user_class_max"),"difficulty_band":t.get("difficulty_band")}))
        ops.append(Operation(op_id="E-"+(t.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(t.get("uid") or ""), properties_delta={"type":"CONTAINS","from_uid":t.get("section_uid"),"to_uid":t.get("uid")}))
    for sk in skills:
        ops.append(Operation(op_id="N-"+(sk.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=sk.get("uid"), properties_delta={"type":"Skill","uid":sk.get("uid"),"title":sk.get("title"),"definition":sk.get("definition"),"applicability_types":sk.get("applicability_types")}))
    for m in methods:
        ops.append(Operation(op_id="N-"+(m.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=m.get("uid"), properties_delta={"type":"Method","uid":m.get("uid"),"title":m.get("title"),"method_text":m.get("method_text"),"applicability_types":m.get("applicability_types")}))
    unit_rows = [{"uid": (u.get("uid") or f"UNIT-{u.get('topic_uid')}-{abs(hash((u.get('type') or '')+(u.get('branch') or '')))%100000}"), "topic_uid": u.get("topic_uid"), "type": u.get("type"), "payload": __import__('json').dumps(u.get("payload", {}), ensure_ascii=False), "complexity": float(u.get("complexity", 0.0) or 0.0)} for u in content_units if u.get("topic_uid") in {t.get("uid") for t in topics}]
    for u in unit_rows:
        ops.append(Operation(op_id="N-"+(u.get("uid") or ""), op_type=OpType.MERGE_NODE, target_id=u.get("uid"), properties_delta={"type":"ContentUnit","uid":u.get("uid"),"type":u.get("type"),"payload":u.get("payload"),"complexity":u.get("complexity")}))
        ops.append(Operation(op_id="E-"+(u.get("uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(u.get("uid") or ""), properties_delta={"type":"HAS_UNIT","from_uid":u.get("topic_uid"),"to_uid":u.get("uid")}))
    for ts in topic_skills:
        ops.append(Operation(op_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(ts.get("topic_uid") or "")+"-"+(ts.get("skill_uid") or ""), properties_delta={"type":"USES_SKILL","from_uid":ts.get("topic_uid"),"to_uid":ts.get("skill_uid"),"weight":ts.get("weight","linked"),"confidence":ts.get("confidence",0.9)}))
    for pr in topic_prereqs:
        tu = pr.get('topic_uid') or pr.get('target_uid')
        pu = pr.get('prereq_uid')
        if tu and pu:
            ops.append(Operation(op_id="E-"+tu+"-"+pu, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+pu, properties_delta={"type":"PREREQ","from_uid":tu,"to_uid":pu,"weight":pr.get("weight",1.0),"confidence":pr.get("confidence",0.9)}))
    for ex in examples:
        ex_uid = ex.get("uid")
        ops.append(Operation(op_id="N-"+ex_uid, op_type=OpType.MERGE_NODE, target_id=ex_uid, properties_delta={"type":"Example","uid":ex_uid,"title":ex.get("title"),"statement":ex.get("statement"),"difficulty_level":ex.get("difficulty")}))
        tu = ex.get("topic_uid")
        if tu:
            ops.append(Operation(op_id="E-"+tu+"-"+ex_uid, op_type=OpType.MERGE_REL, target_id="E-"+tu+"-"+ex_uid, properties_delta={"type":"HAS_EXAMPLE","from_uid":tu,"to_uid":ex_uid}))
    for es in example_skills:
        ops.append(Operation(op_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-"+(es.get("example_uid") or "")+"-"+(es.get("skill_uid") or ""), properties_delta={"type":"LINKED","from_uid":es.get("example_uid"),"to_uid":es.get("skill_uid"),"role":es.get("role","target")}))
    for sm in [x for x in skill_methods if x.get("skill_uid") and x.get("method_uid")]:
        ops.append(Operation(op_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-L-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"LINKED","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"weight":sm.get("weight","linked"),"confidence":sm.get("confidence",0.9)}))
        ops.append(Operation(op_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), op_type=OpType.MERGE_REL, target_id="E-B-"+(sm.get("skill_uid") or "")+"-"+(sm.get("method_uid") or ""), properties_delta={"type":"BASED_ON","from_uid":sm.get("skill_uid"),"to_uid":sm.get("method_uid"),"confidence":sm.get("confidence",0.9)}))
    ensure_tables()
    p = create_draft_proposal("public", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        from json import dumps
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, "DRAFT", dumps([o.model_dump() for o in ops])))
    conn.close()
    from app.workers.commit import commit_proposal
    res = commit_proposal(p.proposal_id)
    return {"ok": bool(res.get("ok")), "proposal_id": p.proposal_id, "ops": len(ops)}

def build_graph_from_neo4j(subject_filter: str | None = None) -> Dict:
    repo = Neo4jRepo()
    params = {"uid": subject_filter}
    rows = repo.read(
        """
        WITH $uid AS filter
        MATCH (s:Subject)
        WHERE filter IS NULL OR s.uid = filter
        WITH collect(s.uid) AS subj_uids,
             collect({id:s.uid, label:s.title, type:'subject'}) AS subjects
        MATCH (s:Subject)-[:CONTAINS]->(sec:Section)
        WHERE s.uid IN subj_uids
        WITH subj_uids, subjects,
             collect(sec.uid) AS section_uids,
             collect({id:sec.uid, label:sec.title, type:'section'}) AS sections,
             collect({id:s.uid+'->'+sec.uid, source:s.uid, target:sec.uid, rel:'contains'}) AS sec_edges
        MATCH (sec:Section)-[:CONTAINS]->(t:Topic)
        WHERE sec.uid IN section_uids
        WITH subj_uids, subjects, sections, sec_edges,
             collect(t.uid) AS topic_uids,
             collect({id:t.uid, label:t.title, type:'topic'}) AS topics,
             collect({id:sec.uid+'->'+t.uid, source:sec.uid, target:t.uid, rel:'contains'}) AS topic_edges
        MATCH (g:Goal)-[:TARGETS]->(t:Topic)
        WHERE t.uid IN topic_uids
        WITH subj_uids, subjects, sections, topics, sec_edges, topic_edges,
             collect({id:g.uid, label:g.title, type:CASE WHEN 'Objective' IN labels(g) THEN 'objective' ELSE 'goal' END}) AS target_nodes,
             collect({id:t.uid+'->'+g.uid, source:t.uid, target:g.uid, rel:'targets'}) AS target_edges
        MATCH (s:Subject)-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t2:Topic)-[:USES_SKILL]->(sk:Skill)
        WHERE s.uid IN subj_uids
        WITH subj_uids, subjects, sections, topics, target_nodes, sec_edges, topic_edges, target_edges,
             collect(DISTINCT {id:sk.uid, label:sk.title, type:'skill'}) AS skills,
             collect(DISTINCT {id:t2.uid+'->'+sk.uid, source:t2.uid, target:sk.uid, rel:'uses_skill'}) AS skill_edges
        MATCH (sk:Skill)-[r:LINKED]->(m:Method)
        WITH subjects, sections, topics, target_nodes, skills, sec_edges, topic_edges, target_edges, skill_edges,
             collect({id:m.uid, label:m.title, type:'method'}) AS methods,
             collect({id:sk.uid+'->'+m.uid, source:sk.uid, target:m.uid, rel:coalesce(r.weight,'linked')}) AS method_edges
        RETURN subjects, sections, topics, target_nodes, skills, methods, sec_edges, topic_edges, target_edges, skill_edges, method_edges
        """,
        params
    )
    repo.close()
    if not rows:
        return {"nodes": [], "edges": []}
    rec = rows[0]
    nodes = []
    edges = []
    for lst, t in [
        (rec.get('subjects', []), None),
        (rec.get('sections', []), None),
        (rec.get('topics', []), None),
        (rec.get('target_nodes', []), None),
        (rec.get('skills', []), None),
        (rec.get('methods', []), None),
    ]:
        for n in lst:
            nodes.append({'data': {'id': n['id'], 'label': n['label'], 'type': n['type']}})
    for lst in [rec.get('sec_edges', []), rec.get('topic_edges', []), rec.get('target_edges', []), rec.get('skill_edges', []), rec.get('method_edges', [])]:
        for e in lst:
            edges.append({'data': {'id': e['id'], 'source': e['source'], 'target': e['target'], 'rel': e['rel']}})
    return {'nodes': nodes, 'edges': edges}

def analyze_knowledge(subject_uid: str | None = None) -> Dict:
    driver = get_driver()
    metrics: Dict = {}
    with driver.session() as session:
        metrics['subjects'] = session.run("MATCH (n:Subject) RETURN count(n) AS c").single()['c']
        metrics['sections'] = session.run("MATCH (n:Section) RETURN count(n) AS c").single()['c']
        metrics['topics'] = session.run("MATCH (n:Topic) RETURN count(n) AS c").single()['c']
        metrics['skills'] = session.run("MATCH (n:Skill) RETURN count(n) AS c").single()['c']
        metrics['methods'] = session.run("MATCH (n:Method) RETURN count(n) AS c").single()['c']
        metrics['goals'] = session.run("MATCH (n:Goal) RETURN count(n) AS c").single()['c']
        metrics['objectives'] = session.run("MATCH (n:Objective) RETURN count(n) AS c").single()['c']
        orphan_sections = [r['uid'] for r in session.run("MATCH (sec:Section) WHERE NOT EXISTS{ (:Subject)-[:CONTAINS]->(sec) } RETURN sec.uid AS uid")]
        orphan_topics = [r['uid'] for r in session.run("MATCH (t:Topic) WHERE NOT EXISTS{ (:Section)-[:CONTAINS]->(t) } RETURN t.uid AS uid")]
        topics_without_targets = [r['uid'] for r in session.run("MATCH (t:Topic) WHERE NOT EXISTS{ (:Goal)-[:TARGETS]->(t) } RETURN t.uid AS uid")]
        skills_without_subject = [r['uid'] for r in session.run("MATCH (sk:Skill) WHERE NOT EXISTS{ (:Topic)-[:USES_SKILL]->(sk) } RETURN sk.uid AS uid")]
        skills_without_methods = [r['uid'] for r in session.run("MATCH (sk:Skill) WHERE NOT EXISTS{ (sk)-[:LINKED]->(:Method) } RETURN sk.uid AS uid")]
        methods_without_links = [r['uid'] for r in session.run("MATCH (m:Method) WHERE NOT EXISTS{ (:Skill)-[:LINKED]->(m) } RETURN m.uid AS uid")]
        metrics['orphan_sections'] = orphan_sections
        metrics['orphan_topics'] = orphan_topics
        metrics['topics_without_targets'] = topics_without_targets
        metrics['skills_without_subject'] = skills_without_subject
        metrics['skills_without_methods'] = skills_without_methods
        metrics['methods_without_links'] = methods_without_links
        total_topics = metrics['topics']
        with_targets = total_topics - len(topics_without_targets)
        metrics['topic_targets_coverage'] = (with_targets / total_topics) if total_topics else 0.0
        total_skills = metrics['skills']
        linked_skills = total_skills - len(skills_without_methods)
        metrics['skill_linkage_coverage'] = (linked_skills / total_skills) if total_skills else 0.0
    driver.close()
    return metrics

def update_dynamic_weight(topic_uid: str, score: float) -> Dict:
    driver = get_driver()
    delta = (50.0 - float(score)) / 100.0
    with driver.session() as session:
        ensure_weight_defaults(session)
        cur = session.run("MATCH (t:Topic {uid:$uid}) RETURN t.uid AS uid, t.title AS title, t.static_weight AS static_weight, t.dynamic_weight AS dynamic_weight", uid=topic_uid).single()
        if not cur:
            driver.close()
            return {'uid': topic_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
        new_dw = cur['dynamic_weight'] + delta
        if new_dw < 0.0:
            new_dw = 0.0
        if new_dw > 1.0:
            new_dw = 1.0
        session.run("MATCH (t:Topic {uid:$uid}) SET t.dynamic_weight = $dw", uid=topic_uid, dw=new_dw)
    driver.close()
    return {'uid': cur['uid'], 'title': cur['title'], 'static_weight': cur['static_weight'], 'dynamic_weight': new_dw}

def update_skill_dynamic_weight(skill_uid: str, score: float) -> Dict:
    driver = get_driver()
    delta = (50.0 - float(score)) / 100.0
    with driver.session() as session:
        ensure_weight_defaults(session)
        cur = session.run("MATCH (s:Skill {uid:$uid}) RETURN s.uid AS uid, s.title AS title, s.static_weight AS static_weight, s.dynamic_weight AS dynamic_weight", uid=skill_uid).single()
        if not cur:
            driver.close()
            return {'uid': skill_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
        new_dw = cur['dynamic_weight'] + delta
        if new_dw < 0.0:
            new_dw = 0.0
        if new_dw > 1.0:
            new_dw = 1.0
        session.run("MATCH (s:Skill {uid:$uid}) SET s.dynamic_weight = $dw", uid=skill_uid, dw=new_dw)
    driver.close()
    recompute_adaptive_for_skill(skill_uid)
    return {'uid': cur['uid'], 'title': cur['title'], 'static_weight': cur['static_weight'], 'dynamic_weight': new_dw}

def get_current_knowledge_level(topic_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (t:Topic {uid:$uid}) RETURN t.uid AS uid, t.title AS title, t.static_weight AS static_weight, t.dynamic_weight AS dynamic_weight", {"uid": topic_uid})
    repo.close()
    rec = rows[0] if rows else {'uid': topic_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
    return {'uid': rec['uid'], 'title': rec['title'], 'static_weight': rec['static_weight'], 'dynamic_weight': rec['dynamic_weight']}

def get_current_skill_level(skill_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (s:Skill {uid:$uid}) RETURN s.uid AS uid, s.title AS title, s.static_weight AS static_weight, s.dynamic_weight AS dynamic_weight", {"uid": skill_uid})
    repo.close()
    rec = rows[0] if rows else {'uid': skill_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
    return {'uid': rec['uid'], 'title': rec['title'], 'static_weight': rec['static_weight'], 'dynamic_weight': rec['dynamic_weight']}

def build_adaptive_roadmap(subject_uid: str | None = None, limit: int = 50) -> List[Dict]:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    if subject_uid:
        rows = repo.read("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) RETURN t.uid AS uid, t.title AS title, t.static_weight AS sw, t.dynamic_weight AS dw", {"su": subject_uid})
    else:
        rows = repo.read("MATCH (t:Topic) RETURN t.uid AS uid, t.title AS title, t.static_weight AS sw, t.dynamic_weight AS dw")
    items = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']} for r in rows]
    items.sort(key=lambda x: (x['dynamic_weight'] or 0.0), reverse=True)
    items = items[:limit]
    roadmap: List[Dict] = []
    for it in items:
        pr = 'high' if (it['dynamic_weight'] or 0.0) >= 0.7 else ('medium' if (it['dynamic_weight'] or 0.0) >= 0.4 else 'low')
        skills_rows = repo.read("MATCH (t:Topic {uid:$uid})-[:USES_SKILL]->(sk:Skill) RETURN DISTINCT sk.uid AS uid, sk.title AS title, sk.static_weight AS sw, sk.dynamic_weight AS dw", {"uid": it['uid']})
        skills = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']} for r in skills_rows]
        method_rows = repo.read("MATCH (t:Topic {uid:$uid})-[:USES_SKILL]->(sk:Skill)-[:LINKED]->(m:Method) RETURN DISTINCT m.uid AS uid, m.title AS title", {"uid": it['uid']})
        methods = [{'uid': r['uid'], 'title': r['title']} for r in method_rows]
        roadmap.append({'topic': it, 'priority': pr, 'skills': skills, 'methods': methods})
    repo.close()
    return roadmap

def build_user_roadmap_stateless(subject_uid: str | None, user_topic_weights: Dict[str, float], user_skill_weights: Dict[str, float] | None = None, limit: int = 50, penalty_factor: float = 0.15) -> List[Dict]:
    if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password.get_secret_value()):
        topics = load_jsonl(get_path('topics.jsonl'))
        sections = load_jsonl(get_path('sections.jsonl'))
        subj_by_section = {s.get('uid'): s.get('subject_uid') for s in sections}
        roadmap: List[Dict] = []
        for t in topics:
            sec_uid = t.get('section_uid')
            subj_uid = subj_by_section.get(sec_uid)
            if subject_uid and subj_uid != subject_uid:
                continue
            tuid = t.get('uid')
            title = t.get('title') or tuid
            base_weight = 0.5
            user_w = float(user_topic_weights.get(tuid, base_weight))
            effective_weight = max(0.0, min(1.0, user_w))
            pr = "high" if user_w < 0.3 else ("medium" if user_w < 0.7 else "low")
            roadmap.append({"topic_uid": tuid, "title": title, "base_weight": base_weight, "user_weight": user_w, "effective_weight": effective_weight, "priority": pr, "prereqs": [], "skills": []})
        roadmap.sort(key=lambda x: x.get("effective_weight", 0.0), reverse=True)
        return roadmap[:limit]
    repo = Neo4jRepo()
    if subject_uid:
        rows = repo.read(("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) RETURN t.uid AS uid, t.title AS title, coalesce(t.static_weight, 0.5) AS sw, coalesce(t.dynamic_weight, t.static_weight, 0.5) AS dw, collect(pre.uid) AS prereqs"), {"su": subject_uid})
    else:
        rows = repo.read(("MATCH (t:Topic) OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) RETURN t.uid AS uid, t.title AS title, coalesce(t.static_weight, 0.5) AS sw, coalesce(t.dynamic_weight, t.static_weight, 0.5) AS dw, collect(pre.uid) AS prereqs"))
    if not rows:
        topics = load_jsonl(get_path('topics.jsonl'))
        sections = load_jsonl(get_path('sections.jsonl'))
        subj_by_section = {s.get('uid'): s.get('subject_uid') for s in sections}
        roadmap: List[Dict] = []
        for t in topics:
            sec_uid = t.get('section_uid')
            subj_uid = subj_by_section.get(sec_uid)
            if subject_uid and subj_uid != subject_uid:
                continue
            tuid = t.get('uid')
            title = t.get('title') or tuid
            base_weight = 0.5
            user_w = float(user_topic_weights.get(tuid, base_weight))
            effective_weight = max(0.0, min(1.0, user_w))
            pr = "high" if user_w < 0.3 else ("medium" if user_w < 0.7 else "low")
            roadmap.append({"topic_uid": tuid, "title": title, "base_weight": base_weight, "user_weight": user_w, "effective_weight": effective_weight, "priority": pr, "prereqs": [], "skills": []})
        repo.close()
        roadmap.sort(key=lambda x: x.get("effective_weight", 0.0), reverse=True)
        return roadmap[:limit]
    topic_index = {r["uid"]: r for r in rows}
    roadmap: List[Dict] = []
    for r in rows:
        tuid = r["uid"]
        base_weight = float(r["dw"] or r["sw"] or 0.5)
        user_w = float(user_topic_weights.get(tuid, base_weight))
        missing = 0
        for pre_uid in r.get("prereqs", []) or []:
            pre_base = 0.5
            if pre_uid in user_topic_weights:
                pre_w = float(user_topic_weights.get(pre_uid, pre_base))
            else:
                pre_row = topic_index.get(pre_uid)
                pre_w = float((pre_row.get("dw") if pre_row else pre_base) or pre_base)
            if pre_w <= 0.3:
                missing += 1
        effective_weight = max(0.0, user_w - penalty_factor * missing)
        pr = "high" if user_w < 0.3 else ("medium" if user_w < 0.7 else "low")
        skills_rows = repo.read("MATCH (t:Topic {uid:$uid})-[:USES_SKILL]->(sk:Skill) RETURN DISTINCT sk.uid AS uid, sk.title AS title, coalesce(sk.dynamic_weight, sk.static_weight, 0.5) AS w", {"uid": tuid})
        skills = []
        for s in skills_rows:
            suid = s["uid"]
            bw = float(s["w"] or 0.5)
            uw = float((user_skill_weights or {}).get(suid, bw))
            skills.append({"uid": suid, "title": s["title"], "base_weight": bw, "user_weight": uw})
        roadmap.append({"topic_uid": tuid, "title": r["title"], "base_weight": base_weight, "user_weight": user_w, "effective_weight": effective_weight, "priority": pr, "prereqs": r.get("prereqs", []) or [], "skills": skills})
    repo.close()
    roadmap.sort(key=lambda x: x.get("effective_weight", 0.0), reverse=True)
    return roadmap[:limit]

def recompute_relationship_weights() -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (sk:Skill)-[r:LINKED]->(m:Method) SET r.adaptive_weight = COALESCE(sk.dynamic_weight, sk.static_weight, 0.5) RETURN count(r) AS c")
    repo.close()
    return {"updated_links": (rows[0]['c'] if rows else 0)}

def recompute_adaptive_for_skill(skill_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (sk:Skill {uid:$uid})-[r:LINKED]->(m:Method) SET r.adaptive_weight = COALESCE(sk.dynamic_weight, sk.static_weight, 0.5) RETURN count(r) AS c", {"uid": skill_uid})
    repo.close()
    return {"updated_links": (rows[0]['c'] if rows else 0)}

def update_user_topic_weight(user_id: str, topic_uid: str, score: float) -> Dict:
    res = compute_topic_user_weight(topic_uid=topic_uid, score=score)
    return {"user_id": user_id, **res}

def update_user_skill_weight(user_id: str, skill_uid: str, score: float) -> Dict:
    res = compute_skill_user_weight(skill_uid=skill_uid, score=score)
    return {"user_id": user_id, **res}

def get_user_topic_level(user_id: str, topic_uid: str) -> Dict:
    try:
        repo = Neo4jRepo()
        rows = repo.read("MATCH (t:Topic {uid:$uid}) RETURN t.title AS title, coalesce(t.dynamic_weight,t.static_weight,0.5) AS bw", {"uid": topic_uid})
        repo.close()
    except Exception:
        rows = []
    if not rows:
        return {"uid": topic_uid, "user_id": user_id, "title": None, "base_weight": 0.5, "level": knowledge_level_from_weight(0.5)}
    bw = float(rows[0]["bw"] or 0.5)
    return {"uid": topic_uid, "user_id": user_id, "title": rows[0]["title"], "base_weight": bw, "level": knowledge_level_from_weight(bw)}

def get_user_skill_level(user_id: str, skill_uid: str) -> Dict:
    try:
        repo = Neo4jRepo()
        rows = repo.read("MATCH (s:Skill {uid:$uid}) RETURN s.title AS title, coalesce(s.dynamic_weight,s.static_weight,0.5) AS bw", {"uid": skill_uid})
        repo.close()
    except Exception:
        rows = []
    if not rows:
        return {"uid": skill_uid, "user_id": user_id, "title": None, "base_weight": 0.5, "level": knowledge_level_from_weight(0.5)}
    bw = float(rows[0]["bw"] or 0.5)
    return {"uid": skill_uid, "user_id": user_id, "title": rows[0]["title"], "base_weight": bw, "level": knowledge_level_from_weight(bw)}

def build_user_roadmap(user_id: str, subject_uid: str | None = None, limit: int = 50, penalty_factor: float = 0.15) -> List[Dict]:
    return build_user_roadmap_stateless(subject_uid=subject_uid, user_topic_weights={}, user_skill_weights={}, limit=limit, penalty_factor=penalty_factor)

def complete_user_topic(user_id: str, topic_uid: str, time_spent_sec: float, errors: int) -> Dict:
    return {"ok": True, "stored": False}

def complete_user_skill(user_id: str, skill_uid: str, time_spent_sec: float, errors: int) -> Dict:
    return {"ok": True, "stored": False}

def search_titles(q: str, limit: int = 20) -> List[Dict]:
    repo = Neo4jRepo()
    rows = repo.read("MATCH (n) WHERE toLower(n.title) CONTAINS toLower($q) RETURN n.uid AS uid, labels(n)[0] AS type, n.title AS title LIMIT $limit", {"q": q, "limit": int(limit)})
    repo.close()
    return rows

def health() -> Dict:
    try:
        repo = Neo4jRepo()
        rows = repo.read("RETURN 1 AS ok")
        repo.close()
        return {"ok": True}
    except Exception:
        return {"ok": False}

def list_items(kind: str, subject_uid: str | None = None, section_uid: str | None = None) -> List[Dict]:
    repo = Neo4jRepo()
    if kind == 'subjects':
        rows = repo.read("MATCH (s:Subject) RETURN s.uid AS uid, s.title AS title ORDER BY s.title")
    elif kind == 'sections':
        if subject_uid:
            rows = repo.read("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(sec:Section) RETURN sec.uid AS uid, sec.title AS title ORDER BY sec.title", {"su": subject_uid})
        else:
            rows = repo.read("MATCH (sec:Section) RETURN sec.uid AS uid, sec.title AS title ORDER BY sec.title")
    elif kind == 'topics':
        if section_uid:
            rows = repo.read("MATCH (sec:Section {uid:$se})-[:CONTAINS]->(t:Topic) RETURN t.uid AS uid, t.title AS title ORDER BY t.title", {"se": section_uid})
        else:
            rows = repo.read("MATCH (t:Topic) RETURN t.uid AS uid, t.title AS title ORDER BY t.title")
    elif kind == 'skills':
        if subject_uid:
            rows = repo.read("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t:Topic)-[:USES_SKILL]->(sk:Skill) RETURN DISTINCT sk.uid AS uid, sk.title AS title ORDER BY sk.title", {"su": subject_uid})
        else:
            rows = repo.read("MATCH (sk:Skill) RETURN sk.uid AS uid, sk.title AS title ORDER BY sk.title")
    elif kind == 'methods':
        rows = repo.read("MATCH (m:Method) RETURN m.uid AS uid, m.title AS title ORDER BY m.title")
    else:
        rows = []
    repo.close()
    return rows

def get_node_details(uid: str) -> Dict:
    repo = Neo4jRepo()
    rows = repo.read("MATCH (n) WHERE n.uid=$uid RETURN labels(n) AS labels, n.title AS title", {"uid": uid})
    if not rows:
        repo.close()
        return {"found": False}
    labels = rows[0]['labels']
    typ = labels[0] if labels else None
    details: Dict = {"found": True, "type": typ, "uid": uid, "title": rows[0]['title']}
    if typ == 'Topic':
        wrows = repo.read("MATCH (t:Topic {uid:$uid}) RETURN t.static_weight AS sw, t.dynamic_weight AS dw", {"uid": uid})
        if wrows:
            details["static_weight"] = wrows[0]['sw']
            details["dynamic_weight"] = wrows[0]['dw']
        g = repo.read("MATCH (g:Goal)-[:TARGETS]->(t:Topic {uid:$uid}) RETURN g.uid AS uid, g.title AS title, labels(g)[0] AS label", {"uid": uid})
        details["targets"] = [{"uid": r['uid'], "title": r['title'], "type": 'goal'} for r in g]
        pr = repo.read("MATCH (t:Topic {uid:$uid})-[:PREREQ]->(p:Topic) RETURN p.uid AS uid, p.title AS title", {"uid": uid})
        details["prereqs"] = pr
        m = repo.read("MATCH (t:Topic {uid:$uid})-[:USES_SKILL]->(sk:Skill)-[:LINKED]->(m:Method) RETURN DISTINCT m.uid AS uid, m.title AS title", {"uid": uid})
        details["methods"] = [{"uid": r['uid'], "title": r['title']} for r in m]
        details["summary"] = {"title": details["title"], "prereqs_count": len(details.get("prereqs", [])), "targets_count": len(details.get("targets", [])), "methods_count": len(details.get("methods", []))}
    elif typ == 'Skill':
        wrows = repo.read("MATCH (s:Skill {uid:$uid}) RETURN s.static_weight AS sw, s.dynamic_weight AS dw", {"uid": uid})
        if wrows:
            details["static_weight"] = wrows[0]['sw']
            details["dynamic_weight"] = wrows[0]['dw']
        lm = repo.read("MATCH (s:Skill {uid:$uid})-[r:LINKED]->(m:Method) RETURN m.uid AS uid, m.title AS title, r.weight AS weight", {"uid": uid})
        details["linked_methods"] = lm
    elif typ == 'Section':
        t = repo.read("MATCH (sec:Section {uid:$uid})-[:CONTAINS]->(t:Topic) RETURN t.uid AS uid, t.title AS title", {"uid": uid})
        details["topics"] = t
    elif typ == 'Subject':
        sec = repo.read("MATCH (s:Subject {uid:$uid})-[:CONTAINS]->(sec:Section) RETURN sec.uid AS uid, sec.title AS title", {"uid": uid})
        sk = repo.read("MATCH (s:Subject {uid:$uid})-[:CONTAINS]->(:Section)-[:CONTAINS]->(:Subsection)-[:CONTAINS]->(t:Topic)-[:USES_SKILL]->(sk:Skill) RETURN DISTINCT sk.uid AS uid, sk.title AS title", {"uid": uid})
        details["sections"] = sec
        details["skills"] = sk
    repo.close()
    return details

def fix_orphan_section(section_uid: str, subject_uid: str) -> Dict:
    driver = get_driver()
    with driver.session() as session:
        session.run("MATCH (sub:Subject {uid:$su}), (sec:Section {uid:$uid}) MERGE (sub)-[:CONTAINS]->(sec)", su=subject_uid, uid=section_uid)
    driver.close()
    return {"fixed": section_uid, "subject": subject_uid}

def compute_static_weights() -> Dict:
    driver = get_driver()
    updated_topics = 0
    updated_skills = 0
    adv_terms = ['логарифм','экспонен','диофант','тригонометр','интеграл','предел','комбинатор','вектор','матриц','дифференц','производн','градиент']
    def score(text: str) -> float:
        t = (text or '').lower()
        tokens = [c for c in t if c.isalnum() or c.isspace()]
        token_count = len(''.join(tokens).split())
        adv = sum(1 for term in adv_terms if term in t)
        base = 0.3
        s = base + min(0.7, 0.02 * token_count + 0.1 * adv)
        return max(0.0, min(1.0, s))
    with driver.session() as session:
        res = session.run("MATCH (t:Topic) RETURN t.uid AS uid, t.title AS title, t.description AS desc")
        for r in res:
            sw = score((r['title'] or '') + ' ' + (r['desc'] or ''))
            session.run("MATCH (t:Topic {uid:$uid}) SET t.static_weight = $sw, t.dynamic_weight = COALESCE(t.dynamic_weight, $sw)", uid=r['uid'], sw=sw)
            updated_topics += 1
        res = session.run("MATCH (s:Skill) RETURN s.uid AS uid, s.title AS title, s.definition AS def")
        for r in res:
            sw = score((r['title'] or '') + ' ' + (r['def'] or ''))
            session.run("MATCH (s:Skill {uid:$uid}) SET s.static_weight = $sw, s.dynamic_weight = COALESCE(s.dynamic_weight, $sw)", uid=r['uid'], sw=sw)
            updated_skills += 1
    with driver.session() as session:
        res = session.run("MATCH (a:Topic)-[:PREREQ]->(b:Topic) RETURN a.uid AS au, b.uid AS bu, a.static_weight AS aw, b.static_weight AS bw")
        for r in res:
            aw = float(r["aw"] or 0.0)
            bw = float(r["bw"] or 0.0)
            if aw > bw:
                session.run("MATCH (t:Topic {uid:$uid}) SET t.static_weight = $bw", uid=r["au"], bw=bw)
                updated_topics += 1
    driver.close()
    return {"topics": updated_topics, "skills": updated_skills}

def analyze_prereqs(subject_uid: str | None = None) -> Dict:
    driver = get_driver()
    cycles: List[List[str]] = []
    cross_subject_errors: List[Dict] = []
    anomalies: List[Dict] = []
    with driver.session() as session:
        if subject_uid:
            rows = session.run("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) RETURN collect(t.uid) AS uids", su=subject_uid).single()
            allowed = set(rows["uids"]) if rows else set()
        else:
            allowed = None
        graph = {}
        res = session.run("MATCH (a:Topic)-[:PREREQ]->(b:Topic) RETURN a.uid AS au, b.uid AS bu")
        for r in res:
            graph.setdefault(r["au"], []).append(r["bu"])
        visited = set()
        stack = set()
        def dfs(u: str, path: List[str]):
            if u in stack:
                cycle_start = path.index(u) if u in path else 0
                cycles.append(path[cycle_start:] + [u])
                return
            if u in visited:
                return
            visited.add(u)
            stack.add(u)
            for v in graph.get(u, []):
                dfs(v, path + [u])
            stack.remove(u)
        for node in list(graph.keys()):
            dfs(node, [])
        res = session.run("MATCH (sa:Subject)-[:CONTAINS]->(:Section)-[:CONTAINS]->(a:Topic)-[:PREREQ]->(b:Topic)<-[:CONTAINS]-(:Section)<-[:CONTAINS]-(sb:Subject) RETURN a.uid AS au, b.uid AS bu, sa.uid AS asu, sb.uid AS bsu")
        for r in res:
            if allowed is None or (r["au"] in allowed and r["bu"] in allowed):
                if r["asu"] != r["bsu"]:
                    cross_subject_errors.append({"topic_uid": r["au"], "prereq_uid": r["bu"], "subject": r["asu"], "prereq_subject": r["bsu"]})
        res = session.run("MATCH (:Topic)-[rel:PREREQ]->(:Topic) WHERE rel.weight < 0 OR rel.weight > 1 RETURN rel")
        anomalies = ["edge" for _ in res]
    driver.close()
    return {"cycles": cycles, "cross_subject_errors": cross_subject_errors, "anomalies": anomalies}

def add_prereqs_heuristic() -> Dict:
    driver = get_driver()
    created = 0
    with driver.session() as session:
        rules = [
            {"match":"квадратн", "target":"TOP-ALG-QUAD-EQ", "prereqs":["TOP-ALG-LIN-EQ","TOP-ALG-FACTOR"]},
            {"match":"логарифм", "target":"TOP-FUNC-LOG", "prereqs":["TOP-FUNC-EXP"]},
            {"match":"экспонен", "target":"TOP-FUNC-EXP", "prereqs":["TOP-AR-POWERS"]},
            {"match":"тожд", "target":"TOP-TRIG-IDENTITIES", "prereqs":["TOP-TRIG-DEFS","TOP-TRIG-UNIT-CIRCLE"]},
        ]
        for rule in rules:
            tgt = session.run("MATCH (t:Topic {uid:$uid}) RETURN t.uid AS uid", uid=rule['target']).single()
            if not tgt:
                continue
            for pre in rule['prereqs']:
                pr = session.run("MATCH (p:Topic {uid:$uid}) RETURN p.uid AS uid", uid=pre).single()
                if not pr:
                    continue
                session.run("MATCH (p:Topic {uid:$pre}), (t:Topic {uid:$tgt}) MERGE (t)-[:PREREQ]->(p)", pre=pre, tgt=rule['target'])
                created += 1
    driver.close()
    return {"created_prereq_edges": created}

def link_remaining_skills_methods() -> Dict:
    driver = get_driver()
    created = 0
    pairs = [
        ("SKL-CIRCLE-PROPS","MET-GEO-CIRCLE-SECANT"),
        ("SKL-CIRCLE-PROPS","MET-GEO-CIRCLE-CIRCUMSCRIBED"),
        ("SKL-COMBI-COUNT","MET-COMB-PIGEONHOLE"),
        ("SKL-DIFF-RULES","MET-FUNC-PIECEWISE-DERIVATIVE"),
        ("SKL-PROB-CALC","MET-PROB-POISSON"),
        ("SKL-MOD-OPS","MET-NUM-EULER-TOTIENT"),
        ("SKL-AREA-CALC","MET-GEO-SOLID-ANGLES"),
        ("SKL-EXP-RULES","MET-ANA-TAYLOR-SERIES"),
        ("SKL-COORD-OPS","MET-GEO-CIRCLE-POWER"),
        ("SKL-TRANSFORM-APPLY","MET-FUNC-PIECEWISE-CONTINUITY"),
        ("SKL-FUNC-TRANSFORM","MET-FUNC-PIECEWISE-CONTINUITY"),
        ("SKL-DIOPH-SOLVE","MET-NUM-FERMAT-LITTLE"),
        ("SKL-LINE-EQ","MET-VEC-TRIPLE-PRODUCT"),
    ]
    with driver.session() as session:
        for su, mu in pairs:
            ok = session.run("MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) RETURN s.uid AS su, m.uid AS mu", su=su, mu=mu).single()
            if not ok:
                continue
            session.run("MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) MERGE (s)-[r:LINKED]->(m) SET r.weight=COALESCE(r.weight,'secondary'), r.confidence=COALESCE(r.confidence,0.8)", su=su, mu=mu)
            created += 1
    driver.close()
    return {"created_links": created}

def link_skill_to_best(skill_uid: str, method_candidates: List[str]) -> Dict:
    driver = get_driver()
    created = False
    with driver.session() as session:
        for mu in method_candidates:
            ok = session.run("MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) RETURN s.uid AS su, m.uid AS mu", su=skill_uid, mu=mu).single()
            if not ok:
                continue
            session.run("MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) MERGE (s)-[r:LINKED]->(m) SET r.weight=COALESCE(r.weight,'primary'), r.confidence=COALESCE(r.confidence,0.9)", su=skill_uid, mu=mu)
            created = True
            break
    driver.close()
    return {"skill": skill_uid, "linked": created}
