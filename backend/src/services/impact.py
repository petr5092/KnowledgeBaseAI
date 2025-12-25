from typing import Dict, List, Tuple, Set, Optional
from src.db.pg import get_proposal
from src.services.diff import build_diff
from src.services.graph.neo4j_repo import neighbors
import time, os

_CACHE: Dict[Tuple[str, int], Tuple[float, Tuple[List[Dict], List[Dict]]]] = {}
_TTL_S = int(os.environ.get("IMPACT_CACHE_TTL_S", "60"))

def _neighbors_cached(uid: str, depth: int) -> Tuple[List[Dict], List[Dict]]:
    key = (uid, depth)
    now = time.time()
    if key in _CACHE:
        ts, data = _CACHE[key]
        if now - ts < _TTL_S:
            return data
    ns, es = neighbors(uid, depth=depth)
    _CACHE[key] = (now, (ns, es))
    return ns, es

def impact_subgraph_for_proposal(proposal_id: str, depth: int = 1, types: Optional[List[str]] = None, max_nodes: Optional[int] = None, max_edges: Optional[int] = None) -> Dict:
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
        ns, es = _neighbors_cached(u, depth=depth)
        for n in ns:
            nid = n.get("id")
            if nid in seen_n:
                continue
            seen_n.add(nid)
            nodes.append(n)
        for e in es:
            key = (e.get("source"), e.get("target"), e.get("kind"))
            if key in seen_e:
                continue
            seen_e.add(key)
            if types and e.get("kind") not in types:
                continue
            edges.append(e)
    if isinstance(max_nodes, int) and max_nodes > 0:
        nodes = nodes[:max_nodes]
    if isinstance(max_edges, int) and max_edges > 0:
        edges = edges[:max_edges]
    return {"nodes": nodes, "edges": edges}
