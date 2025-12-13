import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import Optional, List
from src.services.graph.neo4j_repo import get_driver
from src.services.curriculum.repo import get_graph_view
import os
import json
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
class Method:
    source: str
    target: str
    rel: str
    uid: Optional[str] = None
    title: Optional[str] = None

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
class CurriculumNode:
    kind: str
    canonical_uid: str
    order_index: int

@strawberry.type
class Curriculum:
    code: str
    nodes: List[CurriculumNode]

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
                "MATCH (s:Subject)-[:HAS_SKILL]->(sk:Skill) WHERE s.uid IN subj_uids "
                "WITH subjects, sections, topics, sec_edges, topic_edges, "
                "collect({uid:sk.uid, title:sk.title, type:'skill'}) AS skills, "
                "collect({source:s.uid, target:sk.uid, rel:'has_skill'}) AS skill_edges "
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
        tg = s.run("MATCH (t:Topic {uid:$u})-[:TARGETS]->(g:Goal) RETURN g.uid AS uid, g.title AS title", {"u": uid})
        goals = [Goal(uid=r["uid"], title=r["title"]) for r in tg]
        obj = s.run("MATCH (t:Topic {uid:$u})-[:TARGETS]->(o:Objective) RETURN o.uid AS uid, o.title AS title", {"u": uid})
        objectives = [Objective(uid=r["uid"], title=r["title"]) for r in obj]
        ms = s.run("MATCH (t:Topic {uid:$u})-[:USES_SKILL]->(sk:Skill)-[:LINKED]->(m:Method) RETURN DISTINCT m.uid AS uid, m.title AS title", {"u": uid})
        methods = [Node(uid=r["uid"], title=r["title"], type="method") for r in ms]
        ex_rows = s.run("MATCH (t:Topic {uid:$u})-[:HAS_QUESTION]->(q) RETURN q.uid AS uid, q.title AS title, q.statement AS statement, q.difficulty AS difficulty", {"u": uid}).data()
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
        exq = s.run("MATCH (e:Error {uid:$u})-[:ILLUSTRATED_BY]->(q) RETURN q.uid AS uid, q.title AS title, q.statement AS statement, q.difficulty AS difficulty", {"u": uid}).data()
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

    def curriculum(self, code: str) -> Curriculum:
        res = get_graph_view(code)
        nodes = [CurriculumNode(kind=n["kind"], canonical_uid=n["canonical_uid"], order_index=int(n["order_index"])) for n in res.get("nodes", [])]
        return Curriculum(code=code, nodes=nodes)
    def topic(self, uid: str) -> TopicDetails:
        return _topic_details(uid)
    def error(self, uid: str) -> ErrorNode:
        return _error_details(uid)
    def errorsBySkill(self, skill_uid: str) -> List[ErrorNode]:
        drv = get_driver()
        out: List[ErrorNode] = []
        with drv.session() as s:
            rows = s.run("MATCH (e:Error)-[:TRIGGERS]->(sk:Skill {uid:$u}) RETURN e.uid AS uid", {"u": skill_uid}).data()
            for r in rows:
                out.append(_error_details(r["uid"]))
        drv.close()
        return out
    def errorsByTopic(self, topic_uid: str) -> List[ErrorNode]:
        drv = get_driver()
        out: List[ErrorNode] = []
        with drv.session() as s:
            rows = s.run(
                "MATCH (t:Topic {uid:$u})-[:USES_SKILL]->(sk:Skill)<-[:TRIGGERS]-(e:Error) RETURN DISTINCT e.uid AS uid",
                {"u": topic_uid}
            ).data()
            for r in rows:
                out.append(_error_details(r["uid"]))
        drv.close()
        return out
    def examplesByError(self, error_uid: str) -> List[Example]:
        e = _error_details(error_uid)
        return e.examples

schema = strawberry.Schema(Query)
router = GraphQLRouter(schema)
