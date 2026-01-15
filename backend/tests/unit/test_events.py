from app.events.publisher import publish_graph_committed, get_redis
import json, uuid

def test_publish_graph_committed_pushes_to_list():
    r = get_redis()
    key = "events:graph_committed"
    before = r.llen(key)
    ev = {"tenant_id": "tenant-"+uuid.uuid4().hex[:6], "proposal_id": "P-"+uuid.uuid4().hex[:6], "graph_version": 42}
    publish_graph_committed(ev)
    after = r.llen(key)
    assert after == before + 1
    raw = r.lpop(key)
    data = json.loads(raw)
    assert data["graph_version"] == 42
