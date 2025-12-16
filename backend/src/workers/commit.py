from typing import Dict, List, Any
from src.db.pg import (
    get_conn,
    ensure_tables,
    get_graph_version,
    set_graph_version,
    add_graph_change,
)
from src.services.rebase import rebase_check, RebaseResult
from src.services.integrity import integrity_check_subgraph, check_prereq_cycles
from src.services.graph.neo4j_repo import get_driver
from src.events.publisher import publish_graph_committed
from src.core.correlation import get_correlation_id

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
            tx.run(f"MERGE (n:{typ} {{uid:$uid, tenant_id:$tenant_id}}) SET n += $props", uid=uid, tenant_id=tenant_id, props=props)
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

    # Integrity gate (PREREQ cycles on proposed subgraph)
    proposed_prereq = _collect_prereq_edges(ops)
    if proposed_prereq:
        cyc = check_prereq_cycles(proposed_prereq)
        if cyc:
            _update_proposal_status(proposal_id, "FAILED")
            return {"ok": False, "status": "FAILED", "violations": {"prereq_cycles": cyc}}

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
