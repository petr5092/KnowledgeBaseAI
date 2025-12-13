from typing import Dict, List, Set, Tuple

def _as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def _index_nodes(snapshot: Dict) -> Dict[str, Dict]:
    nodes = _as_list(snapshot.get("nodes"))
    by_id: Dict[str, Dict] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = n.get("id") or n.get("uid")
        if not nid:
            continue
        by_id[str(nid)] = n
    return by_id

def _iter_edges(snapshot: Dict):
    for e in _as_list(snapshot.get("edges")):
        if isinstance(e, dict):
            yield e

def validate_canonical_graph_snapshot(snapshot: Dict) -> Dict:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(snapshot, dict):
        return {"ok": False, "errors": ["snapshot must be an object"], "warnings": []}

    nodes_by_id = _index_nodes(snapshot)
    edges = list(_iter_edges(snapshot))

    if not nodes_by_id:
        errors.append("snapshot.nodes is empty or missing")

    allowed_node_types = {"subject", "section", "topic", "skill", "method", "goal", "objective", "example", "question", "error", "contentunit"}
    allowed_edge_types = {"contains", "has_skill", "uses_skill", "linked", "targets", "prereq", "has_question", "in_topic", "checks", "related_to", "triggered_by"}

    for nid, n in nodes_by_id.items():
        t = (n.get("type") or n.get("node_type") or "").lower()
        if t and t not in allowed_node_types:
            warnings.append(f"unknown node type: {t} (node {nid})")
        if "user" in (t or ""):
            errors.append(f"user node is not allowed in canonical snapshot (node {nid})")

    prereq_graph: Dict[str, List[str]] = {}
    prereq_nodes: Set[str] = set()

    for e in edges:
        src = e.get("source") or e.get("from")
        dst = e.get("target") or e.get("to")
        rel = (e.get("rel") or e.get("type") or "").lower()

        if not src or not dst:
            errors.append("edge missing source/target")
            continue

        src = str(src)
        dst = str(dst)

        if src not in nodes_by_id:
            errors.append(f"edge source not found in nodes: {src}")
        if dst not in nodes_by_id:
            errors.append(f"edge target not found in nodes: {dst}")

        if rel and rel not in allowed_edge_types:
            warnings.append(f"unknown edge type: {rel} ({src} -> {dst})")

        if rel == "prereq":
            prereq_graph.setdefault(src, []).append(dst)
            prereq_nodes.add(src)
            prereq_nodes.add(dst)

    visited: Set[str] = set()
    stack: Set[str] = set()
    cycles: List[List[str]] = []

    def dfs(u: str, path: List[str]):
        if u in stack:
            try:
                i = path.index(u)
            except ValueError:
                i = 0
            cycles.append(path[i:] + [u])
            return
        if u in visited:
            return
        visited.add(u)
        stack.add(u)
        for v in prereq_graph.get(u, []):
            dfs(v, path + [u])
        stack.remove(u)

    for u in list(prereq_graph.keys()):
        dfs(u, [])

    if cycles:
        errors.append(f"prereq graph has cycles: {cycles[:3]}")

    inbound: Dict[str, int] = {nid: 0 for nid in nodes_by_id.keys()}
    outbound: Dict[str, int] = {nid: 0 for nid in nodes_by_id.keys()}
    for e in edges:
        src = str(e.get("source") or e.get("from") or "")
        dst = str(e.get("target") or e.get("to") or "")
        if src in outbound:
            outbound[src] += 1
        if dst in inbound:
            inbound[dst] += 1

    for nid, n in nodes_by_id.items():
        t = (n.get("type") or n.get("node_type") or "").lower()
        if t in {"section", "topic", "skill", "method", "goal", "objective"}:
            if inbound.get(nid, 0) == 0 and outbound.get(nid, 0) == 0:
                warnings.append(f"orphan node: {nid} ({t})")

    return {"ok": not errors, "errors": errors, "warnings": warnings}

