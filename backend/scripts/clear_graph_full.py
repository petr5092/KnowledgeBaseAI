#!/usr/bin/env python3
import os, json
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

def main():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise SystemExit("Neo4j env not configured")
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with drv.session() as s:
        cons = s.run("SHOW CONSTRAINTS").data()
        for r in cons:
            name = r.get("name")
            if name:
                s.run(f"DROP CONSTRAINT {name} IF EXISTS")
        idxs = s.run("SHOW INDEXES").data()
        for r in idxs:
            name = r.get("name")
            if name:
                s.run(f"DROP INDEX {name} IF EXISTS")
        s.run("MATCH (n) DETACH DELETE n")
        cn = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        cr = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    drv.close()
    print(json.dumps({"nodes": int(cn), "rels": int(cr)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
