import os
import pytest

@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'dev')
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setenv('NEO4J_URI', os.getenv('NEO4J_URI',''))
    monkeypatch.setenv('NEO4J_USER', os.getenv('NEO4J_USER',''))
    monkeypatch.setenv('NEO4J_PASSWORD', os.getenv('NEO4J_PASSWORD',''))
    monkeypatch.setenv('PG_DSN', os.getenv('PG_DSN',''))
