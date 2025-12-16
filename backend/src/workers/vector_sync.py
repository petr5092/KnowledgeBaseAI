from typing import Dict, List
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Distance, VectorParams
from src.config.settings import settings
from src.events.publisher import get_redis

def mark_entities_updated(tenant_id: str, targets: List[str], collection: str = "kb_entities") -> int:
    client = QdrantClient(url=str(settings.qdrant_url))
    cols = [c.name for c in client.get_collections().collections]
    if collection not in cols:
        client.create_collection(collection, vectors_config=VectorParams(size=8, distance=Distance.COSINE))
    count = 0
    for t in targets:
        cond = Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)), FieldCondition(key="uid", match=MatchValue(value=t))])
        client.set_payload(collection_name=collection, payload={"updated": True}, points=cond)
        count += 1
    return count

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
        n = mark_entities_updated(tenant_id, targets)
        return {"processed": n}
    return {"processed": 0}
