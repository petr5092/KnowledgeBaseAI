import asyncio
from httpx import AsyncClient
from src.main import app

async def _post(client, url, json):
    return await client.post(url, json=json)

async def test_generate_smart_minimal():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await _post(client, "/kb/generate_smart", {"subject":"Mathematics","language":"ru","import_into_graph":False,"limits":{"sections":2,"topics_per_subsection":3}})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert isinstance(data.get("base_dir"), str)
