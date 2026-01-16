from typing import Dict, List, Set, Tuple
import networkx as nx
import os
from app.core.canonical import ALLOWED_NODE_LABELS, ALLOWED_EDGE_TYPES

def check_canon_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]:
    violations = []
    for n in nodes:
        # Check node labels
        # Assuming n['type'] corresponds to the primary label
        typ = str(n.get("type") or "")
        if typ and typ not in ALLOWED_NODE_LABELS:
            violations.append(f"Node type not allowed: {typ} (uid={n.get('uid')})")
    
    for r in rels:
        typ = str(r.get("type") or "")
        if typ and typ not in ALLOWED_EDGE_TYPES:
            violations.append(f"Edge type not allowed: {typ} (uid={r.get('uid')})")
    return violations

def check_prereq_cycles(rels: List[Dict]) -> List[Tuple[str, str]]:
    """
    rels: list of {'type': 'PREREQ', 'from_uid': str, 'to_uid': str}
    """
    g = nx.DiGraph()
    for r in rels:
        if str(r.get("type")) != "PREREQ":
            continue
        a = str(r.get("from_uid"))
        b = str(r.get("to_uid"))
        if a and b:
            g.add_edge(a, b)
    cycles = list(nx.simple_cycles(g))
    violations: List[Tuple[str, str]] = []
    for cyc in cycles:
        if len(cyc) == 1:
            violations.append((cyc[0], cyc[0]))
        else:
            for i in range(len(cyc)):
                violations.append((cyc[i], cyc[(i + 1) % len(cyc)]))
    return violations

def check_orphan_skills(nodes: List[Dict], rels: List[Dict]) -> List[str]:
    """
    nodes: list of {'type': 'Skill', 'uid': str}
    rels: list of {'type': 'USES_SKILL', 'from_uid': str, 'to_uid': str}
    """
    skills: Set[str] = set()
    for n in nodes:
        if str(n.get("type")) == "Skill":
            uid = str(n.get("uid"))
            if uid:
                skills.add(uid)
    
    connected_skills: Set[str] = set()
    for r in rels:
        if str(r.get("type")) == "USES_SKILL":
            # Topic -> Skill
            to_uid = str(r.get("to_uid"))
            if to_uid:
                connected_skills.add(to_uid)
                
    orphans = sorted(list(skills.difference(connected_skills)))
    return orphans

def check_hierarchy_compliance(nodes: List[Dict], rels: List[Dict]) -> List[str]:
    """
    Ensures:
    - Topic has incoming CONTAINS from Subsection
    - Subsection has incoming CONTAINS from Section
    - Section has incoming CONTAINS from Subject
    
    Only checks nodes present in the list (if a node is created/merged, it must have a parent link in the same changeset OR be valid otherwise).
    Warning: This local check might be too strict for partial updates if not handled carefully.
    For now, we strictly check: IF a node of type T is in 'nodes', it MUST have an incoming CONTAINS in 'rels'.
    """
    violations = []
    
    # Index parents by child_uid
    parents: Dict[str, str] = {} # child -> parent
    for r in rels:
        if str(r.get("type")) == "CONTAINS":
            parents[str(r.get("to_uid"))] = str(r.get("from_uid"))
            
    for n in nodes:
        typ = str(n.get("type"))
        uid = str(n.get("uid"))
        if not uid: continue
        
        if typ == "Topic":
            if uid not in parents:
                violations.append(f"Topic {uid} missing parent Subsection")
        elif typ == "Subsection":
            if uid not in parents:
                violations.append(f"Subsection {uid} missing parent Section")
        elif typ == "Section":
            if uid not in parents:
                violations.append(f"Section {uid} missing parent Subject")
                
    return violations

def integrity_check_subgraph(nodes: List[Dict], rels: List[Dict]) -> Dict:
    canon_violations = check_canon_compliance(nodes, rels)
    cyc = check_prereq_cycles(rels)
    orphans = check_orphan_skills(nodes, rels)
    hierarchy = check_hierarchy_compliance(nodes, rels)
    
    ok = (len(cyc) == 0) and (len(orphans) == 0) and (len(canon_violations) == 0) and (len(hierarchy) == 0)
    return {
        "ok": ok, 
        "prereq_cycles": cyc, 
        "orphan_skills": orphans, 
        "canon_violations": canon_violations,
        "hierarchy_violations": hierarchy
    }

def check_skill_based_on_rules(nodes: List[Dict], rels: List[Dict], min_required: int = 1, max_allowed: int | None = None) -> Dict:
    skills: Set[str] = set()
    for n in nodes:
        if str(n.get("type")) == "Skill":
            uid = str(n.get("uid"))
            if uid:
                skills.add(uid)
    counts: Dict[str, int] = {s: 0 for s in skills}
    for r in rels:
        if str(r.get("type")) == "BASED_ON":
            fu = str(r.get("from_uid"))
            if fu in counts:
                counts[fu] = counts.get(fu, 0) + 1
    too_few = sorted([s for s, c in counts.items() if c < int(min_required)])
    too_many: List[str] = []
    if isinstance(max_allowed, int) and max_allowed > 0:
        too_many = sorted([s for s, c in counts.items() if c > max_allowed])
    ok = (len(too_few) == 0) and (len(too_many) == 0)
    return {"ok": ok, "too_few": too_few, "too_many": too_many}
