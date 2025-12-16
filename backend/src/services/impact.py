from typing import Dict, List, Tuple, Set
from src.db.pg import get_proposal
from src.services.diff import build_diff
from src.services.graph.neo4j_repo import neighbors

def impact_subgraph_for_proposal(proposal_id: str, depth: int = 1) -> Dict:
    d = build_diff(proposal_id)
    uids: Set[str] = set()
    for it in d.get("items", []):
        k = it.get("key") or {}
        fu = str(k.get("from") or it.get("from_node", {}).get("uid") or "")
        tu = str(k.get("to") or it.get("to_node", {}).get("uid") or "")
        if fu:
            uids.add(fu)
        if tu:
            uids.add(tu)
        after = it.get("after") or {}
        uid = str(after.get("uid") or "")
        if uid:
            uids.add(uid)
    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen_n: Set[int] = set()
    seen_e: Set[Tuple[int,int,str]] = set()
    for u in uids:
        ns, es = neighbors(u, depth=depth)
        for n in ns:
            nid = n.get("id")
            if nid in seen_n:
                continue
            seen_n.add(nid)
            nodes.append(n)
        for e in es:
            key = (e.get("from"), e.get("to"), e.get("type"))
            if key in seen_e:
                continue
            seen_e.add(key)
            edges.append(e)
    return {"nodes": nodes, "edges": edges}
