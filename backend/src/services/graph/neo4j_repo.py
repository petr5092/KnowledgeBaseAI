import time
from typing import List, Dict, Tuple, Callable, Any, Optional
from neo4j import GraphDatabase
from src.config.settings import settings
from src.core.correlation import get_correlation_id
from src.core.logging import logger


def get_driver():
    uri = settings.neo4j_uri
    user = settings.neo4j_user
    password = settings.neo4j_password.get_secret_value()
    if not (uri and user and password):
        raise RuntimeError('Missing Neo4j connection environment variables')
    return GraphDatabase.driver(uri, auth=(user, password))

class Neo4jRepo:
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, max_retries: int = 3, backoff_sec: float = 0.8):
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password.get_secret_value()
        if not self.uri or not self.user or not self.password:
            raise RuntimeError('Missing Neo4j connection environment variables')
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.max_retries = max_retries
        self.backoff_sec = backoff_sec

    def close(self):
        self.driver.close()

    def _retry(self, fn: Callable[[Any], Any]) -> Any:
        attempt = 0
        last_exc = None
        while attempt < self.max_retries:
            try:
                with self.driver.session() as session:
                    return fn(session)
            except Exception as e:
                last_exc = e
                attempt += 1
                time.sleep(self.backoff_sec * attempt)
        raise last_exc

    def write(self, query: str, params: Dict | None = None) -> None:
        def _fn(session):
            cid = get_correlation_id() or ""
            logger.info("neo4j_write", correlation_id=cid)
            session.execute_write(lambda tx: tx.run(query, **(params or {})))
        return self._retry(_fn)

    def read(self, query: str, params: Dict | None = None) -> List[Dict]:
        def _fn(session):
            def reader(tx):
                cid = get_correlation_id() or ""
                logger.info("neo4j_read", correlation_id=cid)
                res = tx.run(query, **(params or {}))
                return [dict(r) for r in res]
            return session.execute_read(reader)
        return self._retry(_fn)

    def _chunks(self, rows: List[Dict], size: int) -> List[List[Dict]]:
        return [rows[i:i+size] for i in range(0, len(rows), size)]

    def write_unwind(self, query: str, rows: List[Dict], chunk_size: int = 500) -> None:
        if not rows:
            return
        for chunk in self._chunks(rows, chunk_size):
            def _fn(session):
                cid = get_correlation_id() or ""
                logger.info("neo4j_write_unwind", correlation_id=cid, rows=len(chunk))
                session.execute_write(lambda tx: tx.run(query, rows=chunk))
            self._retry(_fn)

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
    depth = max(0, min(int(depth), 6))
    with drv.session() as s:
        query = (
            "MATCH p=(c {uid:$uid})-[:CONTAINS|PREREQ|HAS_SKILL|LINKED|TARGETS|HAS_SECTION|HAS_TOPIC|REQUIRES_SKILL|HAS_METHOD|HAS_EXAMPLE|HAS_THEORY|HAS_STEP*0.." + str(depth) + "]-(n) "
            "RETURN collect(DISTINCT n) AS ns, collect(DISTINCT relationships(p)) AS rs"
        )
        res = s.run(query, {"uid": center_uid}).single()
        ns = res["ns"] if res else []
        rs = res["rs"] if res else []
        seen = set()
        for n in ns:
            nid = n.id
            if nid in seen:
                continue
            seen.add(nid)
            # kind - это первая метка (например, Topic, Subject)
            kind = list(n.labels)[0] if n.labels else "Unknown"
            nodes.append({
                "id": nid, 
                "uid": n.get("uid"), 
                "title": n.get("title"), # Было label
                "kind": kind,            # Добавили kind
                "labels": list(n.labels)
            })
        added = set()
        for rels in rs:
            for r in rels:
                key = (r.start_node["uid"], r.end_node["uid"], type(r).__name__)
                if key in added:
                    continue
                added.add(key)
                edges.append({
                    "source": r.start_node["uid"], # Было from
                    "target": r.end_node["uid"],   # Было to
                    "kind": type(r).__name__,      # Было type
                    "weight": r.get("weight", 1.0)
                })
    drv.close()
    return nodes, edges

def node_by_uid(uid: str, tenant_id: str) -> Dict:
    drv = get_driver()
    data: Dict = {}
    with drv.session() as s:
        res = s.run("MATCH (n {uid:$uid, tenant_id:$tid}) RETURN properties(n) AS p", {"uid": uid, "tid": tenant_id}).single()
        if res and res.get("p"):
            data = dict(res.get("p"))
    drv.close()
    return data

def relation_by_pair(from_uid: str, to_uid: str, typ: str, tenant_id: str) -> Dict:
    drv = get_driver()
    data: Dict = {}
    with drv.session() as s:
        res = s.run(
            f"MATCH (a {{uid:$fu, tenant_id:$tid}})-[r:{typ}]->(b {{uid:$tu, tenant_id:$tid}}) RETURN properties(r) AS p",
            {"fu": from_uid, "tu": to_uid, "tid": tenant_id},
        ).single()
        if res and res.get("p"):
            data = dict(res.get("p"))
    drv.close()
    return data

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

def get_node_details(uid: str) -> Dict:
    drv = get_driver()
    data = {}
    with drv.session() as s:
        # Получаем свойства узла
        res = s.run("MATCH (n {uid:$uid}) RETURN n", {"uid": uid}).single()
        if not res:
            return {}
        
        node = res["n"]
        data = dict(node)
        data["labels"] = list(node.labels)
        # Kind
        data["kind"] = list(node.labels)[0] if node.labels else "Unknown"
        
        # Получаем входящие связи
        in_res = s.run("MATCH (n {uid:$uid})<-[r]-(other) RETURN type(r) as rel, other.uid as uid, other.title as title", {"uid": uid})
        data["incoming"] = [{"rel": r["rel"], "uid": r["uid"], "title": r["title"]} for r in in_res]
        
        # Получаем исходящие связи
        out_res = s.run("MATCH (n {uid:$uid})-[r]->(other) RETURN type(r) as rel, other.uid as uid, other.title as title", {"uid": uid})
        data["outgoing"] = [{"rel": r["rel"], "uid": r["uid"], "title": r["title"]} for r in out_res]
        
    drv.close()
    return data
