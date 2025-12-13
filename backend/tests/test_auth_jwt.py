import os

import pytest
from fastapi.testclient import TestClient

os.environ["PG_DSN"] = ""
os.environ["JWT_SECRET_KEY"] = "test-secret"

from src.main import app


def test_register_login_me_without_pg(monkeypatch):
    monkeypatch.setenv("PG_DSN", "")
    client = TestClient(app)

    r = client.post("/v1/auth/register", json={"email": "a@example.com", "password": "pass"})
    assert r.status_code == 503

    r = client.post("/v1/auth/login", json={"email": "a@example.com", "password": "pass"})
    assert r.status_code == 503

    r = client.get("/v1/auth/me")
    assert r.status_code == 401


def test_admin_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    client = TestClient(app)

    r = client.post("/v1/admin/purge_users")
    assert r.status_code == 401

    r = client.post("/v1/admin/purge_users", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 401
