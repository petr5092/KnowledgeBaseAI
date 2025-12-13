from neo4j import GraphDatabase
from fastapi.testclient import TestClient
from src.main import app
import os

def test_e2e_topics_by_error():
    uri = os.environ.get('NEO4J_URI')
    user = os.environ.get('NEO4J_USER')
    pwd = os.environ.get('NEO4J_PASSWORD')
    if not uri or not user or not pwd:
        return
    drv = GraphDatabase.driver(uri, auth=(user, pwd))
    with drv.session() as s:
        s.run("MERGE (sub:Subject{uid:'SUBJ-E2E',title:'E2E Subject'})")
        s.run("MERGE (sec:Section{uid:'SEC-E2E',title:'E2E Section'})")
        s.run("MERGE (sub)-[:CONTAINS]->(sec)")
        s.run("MERGE (t:Topic{uid:'TOP-E2E',title:'E2E Topic'})")
        s.run("MERGE (sec)-[:CONTAINS]->(t)")
        s.run("MERGE (sk:Skill{uid:'SKL-E2E',title:'E2E Skill'})")
        s.run("MERGE (sub)-[:HAS_SKILL]->(sk)")
        s.run("MERGE (t)-[:USES_SKILL]->(sk)")
        s.run("MERGE (err:Error{uid:'ERR-E2E',title:'E2E Error'})")
        s.run("MERGE (err)-[:TRIGGERS]->(sk)")
    drv.close()
    client = TestClient(app)
    q = {"query":"query { errorsByTopic(topic_uid:\"TOP-E2E\"){ uid title } topicsByError:error(uid:\"ERR-E2E\"){uid title} }"}
    r = client.post("/v1/graphql", json=q)
    assert r.status_code == 200
    data = r.json()["data"]
    assert any(e["uid"]=="ERR-E2E" for e in data["errorsByTopic"])
