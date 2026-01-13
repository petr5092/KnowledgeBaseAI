#!/usr/bin/env python3
import os
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

def main():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise SystemExit("Neo4j env not configured")
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    drv.close()
    print("Graph cleared")

if __name__ == "__main__":
    main()
