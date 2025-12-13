import os
from typing import List, Dict, Tuple
from neo4j import GraphDatabase

def get_driver():
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER')
    password = os.getenv('NEO4J_PASSWORD')
    if not (uri and user and password):
        raise RuntimeError('Missing Neo4j env')
    return GraphDatabase.driver(uri, auth=(user, password))

def read_graph(subject_uid: str | None = None) -> Tuple[List[Dict], List[Dict]]:
    drv = get_driver()
    nodes: List[Dict] = []
    edges: List[Dict] = []
    with drv.session() as s:
        res = s.run(
            (
                "MATCH (s:Subject) "
                "WITH collect(s) AS subs "
                "MATCH (a)-[r]->(b) "
                "RETURN collect({id:id(a), uid:coalesce(a.uid,''), label:coalesce(a.title,''), labels:labels(a)}) AS ns, "
                "       collect({source:id(a), target:id(b), rel:type(r)}) AS es"
            )
        ).single()
        ns = res["ns"] if res else []
        es = res["es"] if res else []
        nodes = [{"id": n["id"], "uid": n.get("uid"), "label": n.get("label"), "labels": n.get("labels", [])} for n in ns]
        edges = [{"from": e.get("source"), "to": e.get("target"), "type": e.get("rel")} for e in es]
    drv.close()
    return nodes, edges

def relation_context(from_uid: str, to_uid: str) -> Dict:
    drv = get_driver()
    ctx: Dict = {}
    with drv.session() as s:
        res = s.run(
            (
                "MATCH (a {uid:$from})-[r]->(b {uid:$to}) "
                "RETURN type(r) AS rel, properties(r) AS props, a.title AS a_title, b.title AS b_title"
            ), {"from": from_uid, "to": to_uid}
        ).single()
        if res:
            ctx = {"rel": res["rel"], "props": res["props"], "from_title": res["a_title"], "to_title": res["b_title"]}
    drv.close()
    return ctx

def neighbors(center_uid: str, depth: int = 1) -> Tuple[List[Dict], List[Dict]]:
    drv = get_driver()
    nodes: List[Dict] = []
    edges: List[Dict] = []
    with drv.session() as s:
        res = s.run(
            (
                "MATCH p=(c {uid:$uid})-[:CONTAINS|PREREQ|HAS_SKILL|LINKED|TARGETS*0..$depth]-(n) "
                "RETURN collect(DISTINCT n) AS ns, collect(DISTINCT relationships(p)) AS rs"
            ), {"uid": center_uid, "depth": int(depth)}
        ).single()
        ns = res["ns"] if res else []
        rs = res["rs"] if res else []
        seen = set()
        for n in ns:
            nid = n.id
            if nid in seen:
                continue
            seen.add(nid)
            nodes.append({"id": nid, "uid": n.get("uid"), "label": n.get("title"), "labels": list(n.labels)})
        added = set()
        for rels in rs:
            for r in rels:
                key = (r.start_node.id, r.end_node.id, type(r).__name__)
                if key in added:
                    continue
                added.add(key)
                edges.append({"from": r.start_node.id, "to": r.end_node.id, "type": type(r).__name__})
    drv.close()
    return nodes, edges

def purge_user_artifacts() -> Dict:
    drv = get_driver()
    deleted_users = 0
    deleted_rels = 0
    with drv.session() as s:
        res = s.run("MATCH (u:User) DETACH DELETE u RETURN COUNT(u) AS c").single()
        deleted_users = res["c"] if res else 0
        res2 = s.run("MATCH ()-[r:COMPLETED]-() DELETE r RETURN COUNT(r) AS c").single()
        deleted_rels = res2["c"] if res2 else 0
    drv.close()
    return {"deleted_users": deleted_users, "deleted_completed_rels": deleted_rels}
