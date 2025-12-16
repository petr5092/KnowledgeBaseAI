import os, re

def test_no_direct_neo4j_writes_outside_commit_worker():
    root = "/app/src" if os.path.exists("/app/src") else "/workspace"  # not used; fallback to repository
    base = "/workspace"
    base = "/root/KnowledgeBaseAI/backend/src"
    violations = []
    for dirpath, _, filenames in os.walk(base):
        for f in filenames:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(dirpath, f)
            # allow commit worker
            if fp.endswith("workers/commit.py"):
                continue
            with open(fp, "r", encoding="utf-8") as fh:
                content = fh.read()
                if re.search(r"MERGE\s*\(", content) or re.search(r"CREATE\s*\(", content):
                    violations.append(fp)
    assert len(violations) == 0, f"Direct Neo4j writes found: {violations}"
