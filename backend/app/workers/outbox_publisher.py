from typing import Dict
from app.db.pg import outbox_fetch_unpublished, outbox_mark_published, outbox_mark_failed
import time
try:
    from prometheus_client import Counter, Histogram
    OUTBOX_PUBLISH_TOTAL = Counter("outbox_publish_total", "Outbox publish attempts total", ["result"])
    OUTBOX_PUBLISH_LATENCY_MS = Histogram("outbox_publish_latency_ms", "Outbox publish latency ms", ["event_type", "result"])
except Exception:
    class _Dummy:
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): ...
        class _Ctx:
            def __enter__(self): ...
            def __exit__(self, a, b, c): ...
        def time(self): return self._Ctx()
    OUTBOX_PUBLISH_TOTAL = _Dummy()
    OUTBOX_PUBLISH_LATENCY_MS = _Dummy()
from app.events.publisher import publish_graph_committed

def process_once(limit: int = 100) -> Dict:
    events = outbox_fetch_unpublished(limit)
    processed = 0
    for e in events:
        et = e["event_type"]
        pl = e["payload"]
        if et == "graph_committed":
            t0 = time.time()
            try:
                publish_graph_committed(pl)
                outbox_mark_published(e["event_id"])
                processed += 1
                OUTBOX_PUBLISH_TOTAL.labels(result="success").inc()
                OUTBOX_PUBLISH_LATENCY_MS.labels(event_type=et, result="success").observe((time.time() - t0) * 1000.0)
            except Exception as err:
                outbox_mark_failed(e["event_id"], error=str(err))
                OUTBOX_PUBLISH_TOTAL.labels(result="failed").inc()
                OUTBOX_PUBLISH_LATENCY_MS.labels(event_type=et, result="failed").observe((time.time() - t0) * 1000.0)
        else:
            outbox_mark_failed(e["event_id"], error="unsupported_event_type")
            OUTBOX_PUBLISH_TOTAL.labels(result="unsupported").inc()
            OUTBOX_PUBLISH_LATENCY_MS.labels(event_type=et, result="unsupported").observe(0.0)
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
