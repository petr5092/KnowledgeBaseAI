from typing import Dict
from src.db.pg import outbox_fetch_unpublished, outbox_mark_published, outbox_mark_failed
try:
    from prometheus_client import Counter
    OUTBOX_PUBLISH_TOTAL = Counter("outbox_publish_total", "Outbox publish attempts total", ["result"])
except Exception:
    class _Dummy:
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): ...
    OUTBOX_PUBLISH_TOTAL = _Dummy()
from src.events.publisher import publish_graph_committed

def process_once(limit: int = 100) -> Dict:
    events = outbox_fetch_unpublished(limit)
    processed = 0
    for e in events:
        et = e["event_type"]
        pl = e["payload"]
        if et == "graph_committed":
            try:
                publish_graph_committed(pl)
                outbox_mark_published(e["event_id"])
                processed += 1
                OUTBOX_PUBLISH_TOTAL.labels(result="success").inc()
            except Exception as err:
                outbox_mark_failed(e["event_id"], error=str(err))
                OUTBOX_PUBLISH_TOTAL.labels(result="failed").inc()
        else:
            outbox_mark_failed(e["event_id"], error="unsupported_event_type")
            OUTBOX_PUBLISH_TOTAL.labels(result="unsupported").inc()
    return {"processed": processed}

def process_retry(limit: int = 100) -> Dict:
    evs = outbox_fetch_unpublished(limit)
    retried = 0
    for e in evs:
        if e["event_type"] == "graph_committed":
            try:
                publish_graph_committed(e["payload"])
                outbox_mark_published(e["event_id"])
                retried += 1
            except Exception as err:
                outbox_mark_failed(e["event_id"], error=str(err))
        else:
            outbox_mark_failed(e["event_id"], error="unsupported_event_type")
    return {"retried": retried}
