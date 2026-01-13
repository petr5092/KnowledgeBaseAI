import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import Optional, List
from src.services.graph.neo4j_repo import get_driver
import os, json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))), 'kb')

def _load_jsonl(filename: str):
    path = os.path.join(KB_DIR, filename)
    data = []
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

@strawberry.type
class Node:
    uid: str
    title: str
    type: str

@strawberry.type
class Edge:
    source: str
    target: str
    rel: str

@strawberry.type
class GraphView:
    nodes: List[Node]
    edges: List[Edge]

@strawberry.type
class Goal:
    uid: str
    title: str

@strawberry.type
class Objective:
    uid: str
    title: str

@strawberry.type
class Example:
    uid: str
    title: str
    statement: str
    difficulty: float

@strawberry.type
class ErrorNode:
    uid: str
    title: str
    triggers: List[Node]
    examples: List[Example]

@strawberry.type
class TopicDetails:
    uid: str
    title: str
    prereqs: List[Node]
    goals: List[Goal]
    objectives: List[Objective]
    methods: List[Node]
    examples: List[Example]
    errors: List[Node]

def _graph_from_subject(subject_uid: Optional[str]) -> GraphView:
    drv = get_driver()
    nodes: List[Node] = []
    edges: List[Edge] = []
    with drv.session() as s:
        rows = s.run(
            (
                "WITH $uid AS filter "
                "MATCH (s:Subject) WHERE filter IS NULL OR s.uid = filter "
                "WITH collect(s.uid) AS subj_uids "
                "MATCH (s:Subject)-[:CONTAINS]->(sec:Section) WHERE s.uid IN subj_uids "
                "WITH subj_uids, collect(sec.uid) AS section_uids, "
                "collect({uid:s.uid, title:s.title, type:'subject'}) AS subjects, "
                "collect({source:s.uid, target:sec.uid, rel:'contains'}) AS sec_edges "
                "MATCH (sec:Section)-[:CONTAINS]->(t:Topic) WHERE sec.uid IN section_uids "
                "WITH subj_uids, subjects, sec_edges, collect(t.uid) AS topic_uids, "
                "collect({uid:sec.uid, title:sec.title, type:'section'}) AS sections, "
                "collect({uid:t.uid, title:t.title, type:'topic'}) AS topics, "
                "collect({source:sec.uid, target:t.uid, rel:'contains'}) AS topic_edges "
                "MATCH (t2:Topic)-[:USES_SKILL]->(sk:Skill) WHERE t2.uid IN topic_uids "
                "WITH subjects, sections, topics, sec_edges, topic_edges, "
                "collect(DISTINCT {uid:sk.uid, title:sk.title, type:'skill'}) AS skills, "
                "collect(DISTINCT {source:t2.uid, target:sk.uid, rel:'uses_skill'}) AS skill_edges "
                "MATCH (sk:Skill)-[r:LINKED]->(m:Method) "
                "WITH subjects, sections, topics, skills, sec_edges, topic_edges, skill_edges, "
                "collect({uid:m.uid, title:m.title, type:'method'}) AS methods, "
                "collect({source:sk.uid, target:m.uid, rel:coalesce(r.weight,'linked')}) AS method_edges "
                "RETURN subjects, sections, topics, skills, methods, sec_edges, topic_edges, skill_edges, method_edges"
            ), {"uid": subject_uid}
        ).single()
        if rows:
            ns = rows["subjects"] + rows["sections"] + rows["topics"] + rows["skills"] + rows["methods"]
            es = rows["sec_edges"] + rows["topic_edges"] + rows["skill_edges"] + rows["method_edges"]
            nodes = [Node(uid=n["uid"], title=n["title"], type=n["type"]) for n in ns]
            edges = [Edge(source=e["source"], target=e["target"], rel=e["rel"]) for e in es]
    drv.close()
    return GraphView(nodes=nodes, edges=edges)

def _topic_details(uid: str) -> TopicDetails:
    drv = get_driver()
    t_title = ""
    prereqs: List[Node] = []
    goals: List[Goal] = []
    objectives: List[Objective] = []
    methods: List[Node] = []
    with drv.session() as s:
        row = s.run("MATCH (t:Topic {uid:$u}) RETURN t.title AS title", {"u": uid}).single()
        t_title = (row["title"] if row else "") or ""
        pr = s.run("MATCH (t:Topic {uid:$u})-[:PREREQ]->(p:Topic) RETURN p.uid AS uid, p.title AS title", {"u": uid})
        prereqs = [Node(uid=r["uid"], title=r["title"], type="topic") for r in pr]
        tg = s.run("MATCH (g:Goal)-[:TARGETS]->(t:Topic {uid:$u}) RETURN g.uid AS uid, g.title AS title", {"u": uid})
        goals = [Goal(uid=r["uid"], title=r["title"]) for r in tg]
        obj = s.run("MATCH (o:Objective)-[:MEASURES]->(:Skill)<-[:USES_SKILL]-(t:Topic {uid:$u}) RETURN o.uid AS uid, o.title AS title", {"u": uid})
        objectives = [Objective(uid=r["uid"], title=r["title"]) for r in obj]
        ms = s.run("MATCH (t:Topic {uid:$u})-[:USES_SKILL]->(sk:Skill)-[:LINKED]->(m:Method) RETURN DISTINCT m.uid AS uid, m.title AS title", {"u": uid})
        methods = [Node(uid=r["uid"], title=r["title"], type="method") for r in ms]
        ex_rows = s.run("MATCH (t:Topic {uid:$u})-[:HAS_EXAMPLE]->(ex:Example) RETURN ex.uid AS uid, ex.title AS title, ex.statement AS statement, ex.difficulty_level AS difficulty", {"u": uid}).data()
    if not ex_rows:
        ex_json = [e for e in _load_jsonl('examples.jsonl') if e.get('topic_uid') == uid]
        examples = [Example(uid=e.get('uid',''), title=e.get('title',''), statement=e.get('statement',''), difficulty=float(e.get('difficulty', 3))) for e in ex_json]
    else:
        def _norm(x):
            try:
                xf = float(x)
            except Exception:
                return 0.6
            return xf if xf <= 1.0 else max(0.0, min(1.0, xf / 5.0))
        examples = [Example(uid=r.get('uid',''), title=r.get('title',''), statement=r.get('statement',''), difficulty=_norm(r.get('difficulty', 3))) for r in ex_rows]
    errors = []
    with drv.session() as s2:
        err_rows = s2.run(
            "MATCH (t:Topic {uid:$u})-[:USES_SKILL]->(sk:Skill)<-[:TRIGGERS]-(e:Error) RETURN DISTINCT e.uid AS uid, e.title AS title",
            {"u": uid}
        )
        errors = [Node(uid=r["uid"], title=r["title"], type="error") for r in err_rows]
    drv.close()
    return TopicDetails(uid=uid, title=t_title, prereqs=prereqs, goals=goals, objectives=objectives, methods=methods, examples=examples, errors=errors)

def _error_details(uid: str) -> ErrorNode:
    drv = get_driver()
    title = ""
    triggers: List[Node] = []
    examples: List[Example] = []
    with drv.session() as s:
        row = s.run("MATCH (e:Error {uid:$u}) RETURN e.title AS title", {"u": uid}).single()
        title = (row["title"] if row else "") or ""
        trs = s.run("MATCH (e:Error {uid:$u})-[:TRIGGERS]->(sk:Skill) RETURN sk.uid AS uid, sk.title AS title", {"u": uid})
        triggers = [Node(uid=r["uid"], title=r["title"], type="skill") for r in trs]
        exq = s.run("MATCH (e:Error {uid:$u})<-[:LINKED]-(:Example) RETURN DISTINCT ex.uid AS uid, ex.title AS title, ex.statement AS statement, ex.difficulty_level AS difficulty", {"u": uid}).data()
    if not exq:
        ex_json = [e for e in _load_jsonl('examples.jsonl') if uid in (e.get('error_uids') or [])]
        examples = [Example(uid=e.get('uid',''), title=e.get('title',''), statement=e.get('statement',''), difficulty=float(e.get('difficulty', 3))) for e in ex_json]
    else:
        def _norm(x):
            try:
                xf = float(x)
            except Exception:
                return 0.6
            return xf if xf <= 1.0 else max(0.0, min(1.0, xf / 5.0))
        examples = [Example(uid=r.get('uid',''), title=r.get('title',''), statement=r.get('statement',''), difficulty=_norm(r.get('difficulty', 3))) for r in exq]
    drv.close()
    return ErrorNode(uid=uid, title=title, triggers=triggers, examples=examples)

@strawberry.type
class Query:
    @strawberry.field
    def graph(self, subject_uid: Optional[str] = None) -> GraphView:
        return _graph_from_subject(subject_uid)
    def topic(self, uid: str) -> TopicDetails:
        return _topic_details(uid)
    def error(self, uid: str) -> ErrorNode:
        return _error_details(uid)

schema = strawberry.Schema(Query)
router = GraphQLRouter(schema)
