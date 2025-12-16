import os, ast

ALLOWED = {
    os.path.join("workers", "commit.py"),
    os.path.join("api", "admin_graph.py"),
    os.path.join("services", "graph", "utils.py"),
    os.path.join("services", "graph", "neo4j_repo.py"),
}

WRITE_KEYWORDS = ("CREATE ", "MERGE ", " SET ", " DELETE ")

def test_ast_guard_on_write_queries():
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.abspath(os.path.join(here, "..", "..", "src"))
    violations = []
    for dirpath, _, filenames in os.walk(base):
        for f in filenames:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(dirpath, f)
            rel = os.path.relpath(fp, base)
            rel_norm = rel.replace("\\", "/")
            # scope: only graph services and API layer
            if not (rel_norm.startswith("services/graph/") or rel_norm.startswith("api/")):
                continue
            if rel_norm in ALLOWED:
                continue
            with open(fp, "r", encoding="utf-8") as fh:
                try:
                    tree = ast.parse(fh.read(), filename=fp)
                except Exception:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    s = node.value
                    if any(kw in s for kw in WRITE_KEYWORDS):
                        violations.append(fp)
                        break
    assert len(violations) == 0, f"Write queries found outside whitelist: {violations}"
