#!/usr/bin/env python3
import os, json
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

def main():
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with drv.session() as s:
        rows = s.run("CALL db.propertyKeys()").data()
        props = [r.get("propertyKey") or r.get("property") or r.get("name") for r in rows]
    drv.close()
    print(json.dumps({"count": len(props), "keys": props}, ensure_ascii=False))

if __name__ == "__main__":
    main()
