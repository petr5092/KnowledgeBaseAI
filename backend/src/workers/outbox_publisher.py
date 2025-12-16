from typing import Dict
from src.db.pg import outbox_fetch_unpublished, outbox_mark_published, outbox_mark_failed
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
            except Exception as err:
                outbox_mark_failed(e["event_id"], error=str(err))
        else:
            outbox_mark_failed(e["event_id"], error="unsupported_event_type")
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
