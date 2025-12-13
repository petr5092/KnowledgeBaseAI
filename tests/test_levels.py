from fastapi.testclient import TestClient
from src.main import app

def test_levels_endpoints(monkeypatch):
    client = TestClient(app)
    # no Neo4j env: endpoints should still respond (stateless default handled)
    r1 = client.get("/v1/levels/topic/TOP-TEST")
    assert r1.status_code == 200
    r2 = client.get("/v1/levels/skill/SKL-TEST")
    assert r2.status_code == 200
