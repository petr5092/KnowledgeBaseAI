from typing import Dict, List, Any
from src.db.pg import get_proposal
from src.services.graph.neo4j_repo import node_by_uid, relation_by_pair
from src.services.evidence import resolve_evidence

def apply_delta(base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for k, v in (delta or {}).items():
        out[k] = v
    return out

def build_diff(proposal_id: str) -> Dict:
    p = get_proposal(proposal_id)
    if not p:
        return {"items": []}
    tenant_id = p["tenant_id"]
    ops = p.get("operations") or []
    items: List[Dict] = []
    for op in ops:
        t = op.get("op_type")
        pd = op.get("properties_delta") or {}
        if t in ("CREATE_NODE", "MERGE_NODE"):
            after = apply_delta({}, pd)
            items.append({"kind": "NODE", "type": after.get("type") or "Concept", "target_id": op.get("target_id"), "before": None, "after": after, "evidence": op.get("evidence"), "evidence_chunk": resolve_evidence(op.get("evidence"))})
        elif t == "UPDATE_NODE":
            uid = str(op.get("target_id") or "")
            before = node_by_uid(uid, tenant_id)
            after = apply_delta(before, pd)
            items.append({"kind": "NODE", "type": before.get("type") or pd.get("type") or "Concept", "target_id": uid, "before": before or None, "after": after, "evidence": op.get("evidence"), "evidence_chunk": resolve_evidence(op.get("evidence"))})
        elif t in ("CREATE_REL", "MERGE_REL"):
            typ = str(pd.get("type") or "LINKED")
            fu = str(pd.get("from_uid") or "")
            tu = str(pd.get("to_uid") or "")
            after = apply_delta({}, pd)
            items.append({"kind": "REL", "type": typ, "key": {"from": fu, "to": tu}, "before": None, "after": after, "evidence": op.get("evidence"), "evidence_chunk": resolve_evidence(op.get("evidence"))})
        elif t == "UPDATE_REL":
            typ = str(pd.get("type") or "")
            fu = str(pd.get("from_uid") or "")
            tu = str(pd.get("to_uid") or "")
            before = relation_by_pair(fu, tu, typ, tenant_id) if typ else {}
            after = apply_delta(before, pd)
            items.append({"kind": "REL", "type": typ or before.get("type") or "", "key": {"from": fu, "to": tu}, "before": before or None, "after": after, "evidence": op.get("evidence"), "evidence_chunk": resolve_evidence(op.get("evidence"))})
    return {"items": items}
