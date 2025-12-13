from fastapi.testclient import TestClient
from src.main import app

def test_graphql_topic_details(monkeypatch):
    client = TestClient(app)
    q = {"query": "query { topic(uid: \"TOP-TEST\") { title prereqs { uid } goals { uid } objectives { uid } methods { uid } examples { uid } } }"}
    r = client.post("/v1/graphql", json=q)
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
