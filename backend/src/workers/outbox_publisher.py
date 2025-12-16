from typing import Dict
from src.db.pg import outbox_fetch_unpublished, outbox_mark_published
from src.events.publisher import publish_graph_committed

def process_once(limit: int = 100) -> Dict:
    events = outbox_fetch_unpublished(limit)
    processed = 0
    for e in events:
        et = e["event_type"]
        pl = e["payload"]
        if et == "graph_committed":
            publish_graph_committed(pl)
            outbox_mark_published(e["event_id"])
            processed += 1
    return {"processed": processed}
