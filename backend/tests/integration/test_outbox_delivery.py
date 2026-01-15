import json, uuid
from redis import Redis
from app.config.settings import settings
from app.db.pg import ensure_tables, get_conn
from app.workers.outbox_publisher import process_once

def test_outbox_publishes_graph_committed_to_redis():
    ensure_tables()
    tid = "tenant-int"
    uid = "N-"+uuid.uuid4().hex[:6]
    payload = {"tenant_id": tid, "targets": [uid]}
    conn = get_conn(); conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO events_outbox (event_id, tenant_id, event_type, payload, published) VALUES (%s,%s,%s,%s,FALSE)",
            ("EV-int-1", tid, "graph_committed", json.dumps(payload))
        )
    conn.close()
    res = process_once(limit=10)
    assert res["processed"] >= 1
    r = Redis.from_url(str(settings.redis_url))
    raw = r.lpop("events:graph_committed")
    assert raw is not None
    s = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    got = json.loads(s)
    assert got["tenant_id"] == tid
    assert got["targets"] == [uid]
