from typing import Dict, List, Any
from app.db.pg import get_conn
from app.services.integrity import integrity_check_subgraph

def _collect_nodes_and_rels(ops: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    nodes: List[Dict] = []
    rels: List[Dict] = []
    for op in ops:
        t = op.get("op_type")
        pd = op.get("properties_delta") or {}
        mc = op.get("match_criteria") or {}
        
        # Nodes
        if t in ("CREATE_NODE", "MERGE_NODE", "UPDATE_NODE"):
            typ = str(pd.get("type") or pd.get("labels", [None])[0] or "")
            uid = str(pd.get("uid") or op.get("target_id") or op.get("temp_id") or "")
            if typ and uid:
                nodes.append({"type": typ, "uid": uid})
                
        # Rels
        elif t in ("CREATE_REL", "MERGE_REL", "UPDATE_REL"):
            typ = str(pd.get("type") or mc.get("type") or "")
            fu = str(pd.get("from_uid") or mc.get("start_uid") or "")
            tu = str(pd.get("to_uid") or mc.get("end_uid") or "")
            if typ and fu and tu:
                rels.append({"type": typ, "from_uid": fu, "to_uid": tu})
    return {"nodes": nodes, "rels": rels}

def process_once(limit: int = 20) -> Dict:
    conn = get_conn()
    conn.autocommit = True
    processed = 0
    with conn.cursor() as cur:
        cur.execute("SELECT proposal_id, tenant_id, operations_json FROM proposals WHERE status='ASYNC_CHECK_REQUIRED' LIMIT %s", (limit,))
        rows = cur.fetchall()
        for r in rows:
            pid = r[0]; tid = r[1]; ops = list(r[2] or [])
            x = _collect_nodes_and_rels(ops)
            
            res = integrity_check_subgraph(x["nodes"], x["rels"])
            
            if not res["ok"]:
                # Log failures if needed or store in proposal
                cur.execute("UPDATE proposals SET status='FAILED' WHERE proposal_id=%s", (pid,))
            else:
                cur.execute("UPDATE proposals SET status='READY' WHERE proposal_id=%s", (pid,))
            processed += 1
    conn.close()
    return {"processed": processed}
