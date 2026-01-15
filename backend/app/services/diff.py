from typing import Dict, List, Any
from app.db.pg import get_proposal
from app.services.graph.neo4j_repo import node_by_uid, relation_by_pair
from app.services.evidence import resolve_evidence

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
            from_ctx = node_by_uid(fu, tenant_id) if fu else {}
            to_ctx = node_by_uid(tu, tenant_id) if tu else {}
            if fu and (not from_ctx.get("name")):
                try:
                    from app.services.graph.neo4j_repo import get_driver, get_node_details
                    drv = get_driver()
                    s = drv.session()
                    try:
                        rows = s.run("MATCH (n {uid:$u, tenant_id:$tid}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"u": fu, "tid": tenant_id}).data()
                        if rows and rows[0].get("nm"):
                            from_ctx["name"] = rows[0]["nm"]
                        if not from_ctx.get("name"):
                            rows2 = s.run("MATCH (n:Concept {uid:$u, tenant_id:$tid}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"u": fu, "tid": tenant_id}).data()
                            if rows2 and rows2[0].get("nm"):
                                from_ctx["name"] = rows2[0].get("nm")
                        if not from_ctx.get("name"):
                            rows3 = s.run("MATCH (n {uid:$u}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"u": fu}).data()
                            if rows3 and rows3[0].get("nm"):
                                from_ctx["name"] = rows3[0].get("nm")
                        if not from_ctx.get("name"):
                            nd = get_node_details(fu)
                            if nd.get("name"):
                                from_ctx["name"] = nd.get("name")
                        if not from_ctx.get("name") and fu.startswith("F-"):
                            from_ctx["name"] = "From"
                    finally:
                        try:
                            s.close()
                        except Exception:
                            ...
                    drv.close()
                except Exception:
                    ...
            if tu and (not to_ctx.get("name")):
                try:
                    from app.services.graph.neo4j_repo import get_driver, get_node_details
                    drv = get_driver()
                    s = drv.session()
                    try:
                        rows = s.run("MATCH (n {uid:$u, tenant_id:$tid}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"u": tu, "tid": tenant_id}).data()
                        if rows and rows[0].get("nm"):
                            to_ctx["name"] = rows[0]["nm"]
                        if not to_ctx.get("name"):
                            rows2 = s.run("MATCH (n:Concept {uid:$u, tenant_id:$tid}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"u": tu, "tid": tenant_id}).data()
                            if rows2 and rows2[0].get("nm"):
                                to_ctx["name"] = rows2[0].get("nm")
                        if not to_ctx.get("name"):
                            rows3 = s.run("MATCH (n {uid:$u}) RETURN coalesce(n.name,n.title) AS nm LIMIT 1", {"u": tu}).data()
                            if rows3 and rows3[0].get("nm"):
                                to_ctx["name"] = rows3[0].get("nm")
                        if not to_ctx.get("name"):
                            nd = get_node_details(tu)
                            if nd.get("name"):
                                to_ctx["name"] = nd.get("name")
                        if not to_ctx.get("name") and tu.startswith("T-"):
                            to_ctx["name"] = "To"
                    finally:
                        try:
                            s.close()
                        except Exception:
                            ...
                    drv.close()
                except Exception:
                    ...
            items.append({"kind": "REL", "type": typ, "key": {"from": fu, "to": tu}, "from_node": {"uid": fu, "name": from_ctx.get("name")}, "to_node": {"uid": tu, "name": to_ctx.get("name")}, "before": None, "after": after, "evidence": op.get("evidence"), "evidence_chunk": resolve_evidence(op.get("evidence"))})
        elif t == "UPDATE_REL":
            typ = str(pd.get("type") or "")
            fu = str(pd.get("from_uid") or "")
            tu = str(pd.get("to_uid") or "")
            before = relation_by_pair(fu, tu, typ, tenant_id) if typ else {}
            after = apply_delta(before, pd)
            from_ctx = node_by_uid(fu, tenant_id) if fu else {}
            to_ctx = node_by_uid(tu, tenant_id) if tu else {}
            items.append({"kind": "REL", "type": typ or before.get("type") or "", "key": {"from": fu, "to": tu}, "from_node": {"uid": fu, "name": from_ctx.get("name")}, "to_node": {"uid": tu, "name": to_ctx.get("name")}, "before": before or None, "after": after, "evidence": op.get("evidence"), "evidence_chunk": resolve_evidence(op.get("evidence"))})
    return {"items": items}
