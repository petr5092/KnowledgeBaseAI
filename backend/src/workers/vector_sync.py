from typing import Dict, List
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Distance, VectorParams
from src.config.settings import settings
from src.events.publisher import get_redis
from src.services.graph.neo4j_repo import node_by_uid
from src.services.embeddings.provider import get_provider

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
        n = 0
        client = QdrantClient(url=str(settings.qdrant_url))
        cols = [c.name for c in client.get_collections().collections]
        name = str(settings.qdrant_collection_name)
        dim = int(settings.qdrant_default_vector_dim)
        if name not in cols:
            client.create_collection(name, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        else:
            try:
                info = client.get_collection(name)
                dim = int(info.result.config.params.vectors.size)  # type: ignore
            except Exception:
                dim = int(settings.qdrant_default_vector_dim)
        for uid in targets:
            props = node_by_uid(uid, tenant_id)
            name = props.get("name") or props.get("title") or uid
            import uuid
            vec = get_provider(dim_default=dim).embed_text(name)
            pid = uuid.uuid4().int % (10**12)
            client.upsert(collection_name=name, points=[{"id": pid, "vector": vec, "payload": {"tenant_id": tenant_id, "uid": uid, "name": name}}])
            n += 1
        return {"processed": n}
    return {"processed": 0}
