from typing import Dict, List, Any
from src.db.pg import (
    get_conn,
    ensure_tables,
    get_graph_version,
    set_graph_version,
    add_graph_change,
)
from src.services.rebase import rebase_check, RebaseResult
from src.services.integrity import integrity_check_subgraph, check_prereq_cycles, check_dangling_skills
from src.services.graph.neo4j_repo import get_driver
from src.events.publisher import publish_graph_committed
from src.core.correlation import get_correlation_id
from datetime import datetime
import os, time
try:
    from prometheus_client import Counter, Histogram
    INTEGRITY_VIOLATION_TOTAL = Counter("integrity_violation_total", "Integrity gate violations total", ["type"])
    PROPOSAL_AUTOREBASE_TOTAL = Counter("proposal_auto_rebase_total", "Auto rebase (fast) proposals total")
    INTEGRITY_CHECK_LATENCY_MS = Histogram("integrity_check_latency_ms", "Integrity check latency ms")
except Exception:
    class _Dummy: 
        def inc(self, *args, **kwargs): ...
        def labels(self, *args, **kwargs): return self
        class _Ctx:
            def __enter__(self): ...
            def __exit__(self, a, b, c): ...
        def time(self): return self._Ctx()
    INTEGRITY_VIOLATION_TOTAL = _Dummy()
    PROPOSAL_AUTOREBASE_TOTAL = _Dummy()
    INTEGRITY_CHECK_LATENCY_MS = _Dummy()

def _load_proposal(proposal_id: str) -> Dict | None:
    ensure_tables()
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT tenant_id, base_graph_version, status, operations_json FROM proposals WHERE proposal_id=%s", (proposal_id,))
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "tenant_id": row[0],
        "base_graph_version": int(row[1]),
        "status": str(row[2]),
        "operations": row[3],
    }

def _update_proposal_status(proposal_id: str, status: str) -> None:
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("UPDATE proposals SET status=%s WHERE proposal_id=%s", (status, proposal_id))
    conn.close()

def _collect_target_ids(ops: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    for op in ops:
        tid = op.get("target_id")
        if tid and isinstance(tid, str):
            ids.append(tid)
    return ids

def _collect_prereq_edges(ops: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rels: List[Dict[str, str]] = []
    for op in ops:
        t = op.get("op_type")
        if t in ("CREATE_REL", "MERGE_REL", "UPDATE_REL"):
            pd = op.get("properties_delta") or {}
            typ = str(pd.get("type") or "")
            if typ == "PREREQ":
                fu = str(pd.get("from_uid") or "")
                tu = str(pd.get("to_uid") or "")
                if fu and tu:
                    rels.append({"type": "PREREQ", "from_uid": fu, "to_uid": tu})
    return rels

def _apply_ops_tx(tx, tenant_id: str, ops: List[Dict[str, Any]]) -> None:
    for op in ops:
        t = op.get("op_type")
        pd = op.get("properties_delta") or {}
        if t in ("CREATE_NODE", "MERGE_NODE"):
            typ = str(pd.get("type") or "Concept")
            uid = str(pd.get("uid") or op.get("target_id") or "")
            if not uid:
                uid = "N-" + __import__("uuid").uuid4().hex[:16]
            props = dict(pd)
            props["uid"] = uid
            props["tenant_id"] = tenant_id
            props.setdefault("lifecycle_status", "ACTIVE")
            props.setdefault("created_at", datetime.utcnow().isoformat())
            tx.run(f"MERGE (n:{typ} {{uid:$uid, tenant_id:$tenant_id}}) SET n += $props", uid=uid, tenant_id=tenant_id, props=props)
            ev = op.get("evidence") or {}
            cid = ev.get("source_chunk_id")
            quote = ev.get("quote")
            if cid and quote:
                tx.run("MERGE (sc:SourceChunk {uid:$cid, tenant_id:$tid}) SET sc.quote=$quote", cid=cid, tid=tenant_id, quote=quote)
                tx.run("MATCH (n {uid:$uid, tenant_id:$tid}), (sc:SourceChunk {uid:$cid, tenant_id:$tid}) MERGE (n)-[:EVIDENCED_BY]->(sc)", uid=uid, cid=cid, tid=tenant_id)
        elif t == "UPDATE_NODE":
            uid = str(op.get("target_id") or "")
            props = dict(pd)
            tx.run("MATCH (n {uid:$uid, tenant_id:$tenant_id}) SET n += $props", uid=uid, tenant_id=tenant_id, props=props)
        elif t in ("CREATE_REL", "MERGE_REL"):
            typ = str(pd.get("type") or "LINKED")
            fu = str(pd.get("from_uid") or "")
            tu = str(pd.get("to_uid") or "")
            rid = pd.get("uid") or f"E-{__import__('uuid').uuid4().hex[:16]}"
            props = dict(pd)
            props["uid"] = rid
            tx.run(
                f"MATCH (a {{uid:$fu, tenant_id:$tid}}), (b {{uid:$tu, tenant_id:$tid}}) "
                f"MERGE (a)-[r:{typ} {{uid:$rid}}]->(b) "
                f"SET r += $props",
                fu=fu, tu=tu, rid=rid, props=props, tid=tenant_id
            )
        elif t == "UPDATE_REL":
            typ = str(pd.get("type") or "")
            fu = str(pd.get("from_uid") or "")
            tu = str(pd.get("to_uid") or "")
            rid = str(pd.get("uid") or "")
            props = dict(pd)
            if typ:
                tx.run(
                    f"MATCH (a {{uid:$fu, tenant_id:$tid}})-[r:{typ} {{uid:$rid}}]->(b {{uid:$tu, tenant_id:$tid}}) "
                    f"SET r += $props",
                    fu=fu, tu=tu, rid=rid, props=props, tid=tenant_id
                )
            else:
                tx.run(
                    "MATCH (a {uid:$fu, tenant_id:$tid})-[r {uid:$rid}]->(b {uid:$tu, tenant_id:$tid}) "
                    "SET r += $props",
                    fu=fu, tu=tu, rid=rid, props=props, tid=tenant_id
                )

def commit_proposal(proposal_id: str) -> Dict:
    p = _load_proposal(proposal_id)
    if not p:
        return {"ok": False, "error": "proposal not found"}
    tenant_id = p["tenant_id"]
    base_ver = int(p["base_graph_version"])
    ops = list(p["operations"] or [])

    # Rebase check
    target_ids = _collect_target_ids(ops)
    rb = rebase_check(tenant_id, base_ver, target_ids)
    if rb == RebaseResult.CONFLICT:
        _update_proposal_status(proposal_id, "CONFLICT")
        return {"ok": False, "status": "CONFLICT"}
    if rb == RebaseResult.FAST_REBASE:
        PROPOSAL_AUTOREBASE_TOTAL.inc()

    # Integrity gate (PREREQ cycles on proposed subgraph)
    threshold_ms = int(os.environ.get("INTEGRITY_CHECK_THRESHOLD_MS", "500"))
    with INTEGRITY_CHECK_LATENCY_MS.time():
        t0 = time.time()
        proposed_prereq = _collect_prereq_edges(ops)
        if proposed_prereq:
            cyc = check_prereq_cycles(proposed_prereq)
            if cyc:
                _update_proposal_status(proposal_id, "FAILED")
                INTEGRITY_VIOLATION_TOTAL.labels(type="prereq_cycle").inc()
                return {"ok": False, "status": "FAILED", "violations": {"prereq_cycles": cyc}}
        nodes = []
        for op in ops:
            pd = op.get("properties_delta") or {}
            if (op.get("op_type") in ("CREATE_NODE", "MERGE_NODE", "UPDATE_NODE")) and str(pd.get("type")) == "Skill":
                uid = str(pd.get("uid") or op.get("target_id") or "")
                nodes.append({"type": "Skill", "uid": uid})
        based_on = []
        for op in ops:
            pd = op.get("properties_delta") or {}
            if (op.get("op_type") in ("CREATE_REL", "MERGE_REL", "UPDATE_REL")) and str(pd.get("type")) == "BASED_ON":
                fu = str(pd.get("from_uid") or "")
                tu = str(pd.get("to_uid") or "")
                if fu and tu:
                    based_on.append({"type": "BASED_ON", "from_uid": fu, "to_uid": tu})
        if nodes:
            dangling = check_dangling_skills(nodes, based_on)
            if dangling:
                _update_proposal_status(proposal_id, "FAILED")
                INTEGRITY_VIOLATION_TOTAL.labels(type="dangling_skill").inc()
                return {"ok": False, "status": "FAILED", "violations": {"dangling_skills": dangling}}
        sleep_ms = int(os.environ.get("INTEGRITY_TEST_SLEEP_MS", "0"))
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)
        elapsed_ms = int((time.time() - t0) * 1000)
        if elapsed_ms > threshold_ms:
            _update_proposal_status(proposal_id, "ASYNC_CHECK_REQUIRED")
            return {"ok": False, "status": "ASYNC_CHECK_REQUIRED", "elapsed_ms": elapsed_ms}

    # Apply in single transaction
    drv = get_driver()
    try:
        def writer(session):
            def run(tx):
                _apply_ops_tx(tx, tenant_id, ops)
            session.execute_write(run)
        with drv.session() as s:
            writer(s)
    except Exception as e:
        _update_proposal_status(proposal_id, "FAILED")
        drv.close()
        return {"ok": False, "status": "FAILED", "error": str(e)}
    drv.close()

    # Audit & graph_version update
    conn = get_conn()
    conn.autocommit = True
    new_ver = max(get_graph_version(tenant_id), base_ver) + 1
    set_graph_version(tenant_id, new_ver)
    for tid in target_ids:
        add_graph_change(tenant_id, new_ver, tid)
    with conn.cursor() as cur:
        import uuid, json
        tx_id = "TX-" + uuid.uuid4().hex[:16]
        cur.execute(
            "INSERT INTO audit_log (tx_id, tenant_id, proposal_id, operations_applied, revert_operations, correlation_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (tx_id, tenant_id, proposal_id, json.dumps(ops), json.dumps([]), get_correlation_id() or ""),
        )
    conn.close()
    _update_proposal_status(proposal_id, "DONE")
    publish_graph_committed({"tenant_id": tenant_id, "proposal_id": proposal_id, "graph_version": new_ver, "targets": target_ids, "correlation_id": get_correlation_id() or ""})
    return {"ok": True, "status": "DONE", "graph_version": new_ver}
