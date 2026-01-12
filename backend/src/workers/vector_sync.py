from typing import Dict, List
from src.events.publisher import get_redis
from src.config.settings import settings
from src.services.vector.indexer import index_entities

def mark_entities_updated(tenant_id: str, targets: List[str], collection: str = "kb_entities") -> int:
    res = index_entities(tenant_id=tenant_id, uids=targets, collection=collection)
    return int(res.get("processed", 0))

def consume_graph_committed() -> Dict:
    r = get_redis()
    raw = r.rpop("events:graph_committed")
    if not raw:
        return {"processed": 0}
    import json
    ev = json.loads(raw)
    tenant_id = ev.get("tenant_id")
    targets = ev.get("targets") or []
    if tenant_id and targets:
        res = index_entities(tenant_id=tenant_id, uids=targets, collection=str(settings.qdrant_collection_name), dim=int(settings.qdrant_default_vector_dim))
        return {"processed": int(res.get("processed", 0))}
    return {"processed": 0}
