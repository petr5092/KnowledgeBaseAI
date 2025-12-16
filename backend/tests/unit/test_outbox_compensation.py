from src.db.pg import ensure_tables, get_conn
from src.workers.outbox_publisher import process_once
import json

def test_outbox_marks_failed_on_unsupported_event():
    ensure_tables()
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO events_outbox (event_id, tenant_id, event_type, payload, published) VALUES (%s,%s,%s,%s,FALSE)",
            ("EV-unsupported-1", "tenant-x", "unsupported", json.dumps({"x":1}))
        )
    conn.close()
    res = process_once(limit=10)
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT attempts, last_error, published FROM events_outbox WHERE event_id=%s", ("EV-unsupported-1",))
        row = cur.fetchone()
    conn.close()
    assert row is not None
    assert int(row[0]) >= 1
    assert str(row[1]) == "unsupported_event_type"
    assert row[2] is False
