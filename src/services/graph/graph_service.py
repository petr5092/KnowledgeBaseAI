from typing import Dict, List
import networkx as nx

def dag_check(edges: List[Dict]) -> List[List[str]]:
    g = nx.DiGraph()
    for e in edges:
        g.add_edge(e["from"], e["to"])
    cycles = list(nx.simple_cycles(g))
    return cycles

def connectivity_stats(nodes: List[str], edges: List[Dict]) -> Dict:
    g = nx.Graph()
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e["from"], e["to"])
    comps = list(nx.connected_components(g))
    return {"components": len(comps), "largest": max((len(c) for c in comps), default=0)}

def cognitive_distance(root: str, leaves: List[str], edges: List[Dict]) -> Dict[str, int]:
    g = nx.DiGraph()
    for e in edges:
        g.add_edge(e["from"], e["to"])
    dists = {}
    for leaf in leaves:
        try:
            dists[leaf] = nx.shortest_path_length(g, source=root, target=leaf)
        except Exception:
            dists[leaf] = -1
    return dists
