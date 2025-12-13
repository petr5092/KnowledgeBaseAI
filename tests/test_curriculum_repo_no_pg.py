from fastapi.testclient import TestClient
from src.main import app
import os

def test_admin_curriculum_without_pg(monkeypatch):
    monkeypatch.setenv('PG_DSN', '')
    client = TestClient(app)
    r = client.post("/v1/admin/curriculum", json={"code":"TEST","title":"T","standard":"S","language":"ru"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is False
