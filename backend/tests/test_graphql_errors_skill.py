from fastapi.testclient import TestClient
from src.main import app

def test_graphql_errors_by_skill(monkeypatch):
    client = TestClient(app)
    q = {"query": "query { errorsBySkill(skill_uid: \"SKL-TEST\") { uid title examples { uid } } }"}
    r = client.post("/v1/graphql", json=q)
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
