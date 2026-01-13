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
    s = drv.session()
    try:
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
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return nodes, edges

def relation_context(from_uid: str, to_uid: str) -> Dict:
    drv = get_driver()
    ctx: Dict = {}
    s = drv.session()
    try:
        res = s.run(
            (
                "MATCH (a {uid:$from})-[r]->(b {uid:$to}) "
                "RETURN type(r) AS rel, properties(r) AS props, a.title AS a_title, b.title AS b_title"
            ), {"from": from_uid, "to": to_uid}
        ).single()
        if res:
            ctx = {"rel": res["rel"], "props": res["props"], "from_title": res["a_title"], "to_title": res["b_title"]}
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return ctx

def neighbors(center_uid: str, depth: int = 1) -> Tuple[List[Dict], List[Dict]]:
    drv = get_driver()
    nodes: List[Dict] = []
    edges: List[Dict] = []
    depth = max(0, min(int(depth), 6))
    s = drv.session()
    try:
        query = (
            "MATCH p=(c {uid:$uid})-[*0.." + str(depth) + "]-(n) "
            "RETURN collect(DISTINCT n) AS ns, collect(DISTINCT relationships(p)) AS rs"
        )
        res = s.run(query, {"uid": center_uid})
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        ns = row["ns"] if row else []
        rs = row["rs"] if row else []
        seen = set()
        for n in ns:
            nid = getattr(n, "element_id", None) or n.id
            if nid in seen:
                continue
            seen.add(nid)
            # kind - это первая метка (например, Topic, Subject)
            kind = list(n.labels)[0] if n.labels else "Unknown"
            nodes.append({
                "id": nid, 
                "uid": n.get("uid"), 
                "name": n.get("name"), 
                "title": n.get("title"),
                "kind": kind,            # Добавили kind
                "labels": list(n.labels)
            })
        added = set()
        for rels in rs:
            for r in rels:
                key = (r.start_node["uid"], r.end_node["uid"], r.type)
                if key in added:
                    continue
                added.add(key)
                edges.append({
                    "source": r.start_node["uid"], # Было from
                    "target": r.end_node["uid"],   # Было to
                    "kind": r.type,                # Было type
                    "weight": r.get("weight", 1.0)
                })
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return nodes, edges

def node_by_uid(uid: str, tenant_id: str) -> Dict:
    drv = get_driver()
    data: Dict = {}
    s = drv.session()
    try:
        rows = s.run(
            "MATCH (n) WHERE n.uid=$uid AND (n.tenant_id=$tid OR n.tenant_id IS NULL) "
            "RETURN properties(n) AS p, labels(n) AS labels ORDER BY coalesce(n.created_at,'') DESC LIMIT 1",
            {"uid": uid, "tid": tenant_id}
        ).data()
        if rows:
            r0 = rows[0]
            if r0.get("p"):
                data = dict(r0["p"])
                data["labels"] = r0.get("labels", [])
            if data and not data.get("name"):
                nm = data.get("title")
                if nm:
                    data["name"] = nm
        if not data:
            rows2 = s.run(
                "MATCH (n) WHERE n.uid=$uid RETURN properties(n) AS p, labels(n) AS labels ORDER BY coalesce(n.created_at,'') DESC LIMIT 1",
                {"uid": uid}
            ).data()
            if rows2:
                r2 = rows2[0]
                if r2.get("p"):
                    data = dict(r2["p"])
                    data["labels"] = r2.get("labels", [])
        if not data:
            rows3 = s.run("MATCH (n {uid:$uid}) RETURN properties(n) AS p, labels(n) AS labels ORDER BY coalesce(n.created_at,'') DESC LIMIT 1", {"uid": uid}).data()
            if rows3:
                r3 = rows3[0]
                if r3.get("p"):
                    data = dict(r3["p"])
                    data["labels"] = r3.get("labels", [])
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    if not data:
        try:
            drv2 = get_driver()
            s2 = drv2.session()
            try:
                rows = s2.run("MATCH (n {uid:$uid}) RETURN properties(n) AS p, labels(n) AS labels LIMIT 1", {"uid": uid}).data()
                if rows:
                    r = rows[0]
                    if r.get("p"):
                        data = dict(r["p"])
                        data["labels"] = r.get("labels", [])
            finally:
                try:
                    s2.close()
                except Exception:
                    ...
        finally:
            try:
                drv2.close()
            except Exception:
                ...
    if data and not data.get("name"):
        try:
            drv3 = get_driver()
            s3 = drv3.session()
            try:
                rows = s3.run("MATCH (n {uid:$uid}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"uid": uid}).data()
                if rows and rows[0].get("nm"):
                    data["name"] = rows[0]["nm"]
            finally:
                try:
                    s3.close()
                except Exception:
                    ...
        finally:
            try:
                drv3.close()
            except Exception:
                ...
    if not data:
        data = {"uid": uid, "lifecycle_status": "ACTIVE", "labels": ["Concept"]}
    else:
        if not data.get("lifecycle_status"):
            data["lifecycle_status"] = "ACTIVE"
        if not data.get("created_at"):
            from datetime import datetime
            data["created_at"] = datetime.utcnow().isoformat()
        if not data.get("labels"):
            data["labels"] = ["Concept"]
    if "created_at" not in data or not data.get("created_at"):
        from datetime import datetime
        data["created_at"] = datetime.utcnow().isoformat()
    return data

def relation_by_pair(from_uid: str, to_uid: str, typ: str, tenant_id: str) -> Dict:
    drv = get_driver()
    data: Dict = {}
    s = drv.session()
    try:
        res = s.run(
            f"MATCH (a {{uid:$fu, tenant_id:$tid}})-[r:{typ}]->(b {{uid:$tu, tenant_id:$tid}}) RETURN properties(r) AS p",
            {"fu": from_uid, "tu": to_uid, "tid": tenant_id},
        )
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        if row:
            try:
                data = dict(row["p"])
            except Exception:
                ...
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return data

def purge_user_artifacts() -> Dict:
    drv = get_driver()
    deleted_users = 0
    deleted_rels = 0
    s = drv.session()
    try:
        res = s.run("MATCH (u:User) DETACH DELETE u RETURN COUNT(u) AS c")
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        deleted_users = row["c"] if row else 0
        res2 = s.run("MATCH ()-[r:COMPLETED]-() DELETE r RETURN COUNT(r) AS c")
        row2 = None
        try:
            row2 = res2.single()
        except Exception:
            try:
                row2 = next(iter(res2))
            except Exception:
                row2 = None
        deleted_rels = row2["c"] if row2 else 0
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return {"deleted_users": deleted_users, "deleted_completed_rels": deleted_rels}

def get_node_details(uid: str) -> Dict:
    drv = get_driver()
    data = {}
    s = drv.session()
    try:
        # Получаем свойства узла
        res = s.run("MATCH (n {uid:$uid}) RETURN n", {"uid": uid})
        row = None
        try:
            row = res.single()
        except Exception:
            try:
                row = next(iter(res))
            except Exception:
                row = None
        if not row:
            return {}
        node = row["n"]
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
    finally:
        try:
            s.close()
        except Exception:
            ...
    drv.close()
    return data
