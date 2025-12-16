from typing import Dict, List, Any
from src.db.pg import get_conn
from src.services.integrity import check_prereq_cycles, check_dangling_skills

def _collect_nodes_and_rels(ops: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    nodes: List[Dict] = []
    rels: List[Dict] = []
    for op in ops:
        t = op.get("op_type")
        pd = op.get("properties_delta") or {}
        if t in ("CREATE_NODE", "MERGE_NODE", "UPDATE_NODE"):
            typ = str(pd.get("type") or "")
            uid = str(pd.get("uid") or op.get("target_id") or "")
            if typ and uid:
                nodes.append({"type": typ, "uid": uid})
        elif t in ("CREATE_REL", "MERGE_REL", "UPDATE_REL"):
            typ = str(pd.get("type") or "")
            fu = str(pd.get("from_uid") or "")
            tu = str(pd.get("to_uid") or "")
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
            cyc = check_prereq_cycles([rel for rel in x["rels"] if rel.get("type")=="PREREQ"])
            skills = [{"type": n["type"], "uid": n["uid"]} for n in x["nodes"] if n["type"]=="Skill"]
            based = [{"type": rel["type"], "from_uid": rel["from_uid"], "to_uid": rel["to_uid"]} for rel in x["rels"] if rel["type"]=="BASED_ON"]
            if cyc or check_dangling_skills(skills, based):
                cur.execute("UPDATE proposals SET status='FAILED' WHERE proposal_id=%s", (pid,))
            else:
                cur.execute("UPDATE proposals SET status='READY' WHERE proposal_id=%s", (pid,))
            processed += 1
    conn.close()
    return {"processed": processed}
