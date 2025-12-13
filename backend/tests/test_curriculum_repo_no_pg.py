from fastapi.testclient import TestClient
import os

os.environ["PG_DSN"] = ""

from src.main import app

def test_admin_curriculum_without_pg(monkeypatch):
    monkeypatch.setenv('PG_DSN', '')
    client = TestClient(app)
    r = client.post("/v1/admin/curriculum", json={"code":"TEST","title":"T","standard":"S","language":"ru"})
    assert r.status_code == 401
