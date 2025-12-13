from fastapi.testclient import TestClient
from src.main import app

def test_graphql_error_details(monkeypatch):
    client = TestClient(app)
    q = {"query": "query { error(uid: \"ERR-TEST\") { title triggers { uid } examples { uid } } }"}
    r = client.post("/v1/graphql", json=q)
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
