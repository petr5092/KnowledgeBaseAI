#!/usr/bin/env python3
import os, json, time
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DB = os.getenv("NEO4J_DB", "neo4j")

def main():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise SystemExit("Neo4j env not configured")
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with drv.session(database="system") as s:
        s.run(f"DROP DATABASE {NEO4J_DB} IF EXISTS")
        s.run(f"CREATE DATABASE {NEO4J_DB} IF NOT EXISTS WAIT")
    time.sleep(0.5)
    with drv.session(database=NEO4J_DB) as s2:
        rows = s2.run("SHOW PROPERTY KEYS").data()
        props = [r.get("propertyKey") or r.get("name") for r in rows]
    drv.close()
    print(json.dumps({"database": NEO4J_DB, "property_keys": props}, ensure_ascii=False))

if __name__ == "__main__":
    main()
