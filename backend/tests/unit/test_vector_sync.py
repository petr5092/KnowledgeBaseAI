from src.events.publisher import get_redis, publish_graph_committed
from src.workers.vector_sync import consume_graph_committed
import uuid, json

def test_consume_graph_committed_no_targets():
    r = get_redis()
    r.lpush("events:graph_committed", json.dumps({"tenant_id":"t-"+uuid.uuid4().hex[:6]}))
    res = consume_graph_committed()
    assert res["processed"] == 0

def test_consume_graph_committed_with_targets():
    r = get_redis()
    ev = {"tenant_id":"t-"+uuid.uuid4().hex[:6], "targets":["C-DEMO"]}
    publish_graph_committed(ev)
    res = consume_graph_committed()
    assert "processed" in res
