import os, re

def test_no_direct_neo4j_writes_outside_commit_worker():
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.abspath(os.path.join(here, "..", "..", "src"))
    violations = []
    for dirpath, _, filenames in os.walk(base):
        for f in filenames:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(dirpath, f)
            # allow commit worker and admin graph utilities
            if fp.endswith("workers/commit.py") or fp.endswith("api/admin_graph.py") or fp.endswith("services/graph/utils.py"):
                continue
            with open(fp, "r", encoding="utf-8") as fh:
                content = fh.read()
                if re.search(r"MERGE\s*\(", content) or re.search(r"CREATE\s*\(", content):
                    violations.append(fp)
    assert len(violations) == 0, f"Direct Neo4j writes found: {violations}"
