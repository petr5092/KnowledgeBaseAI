from typing import Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from src.config.settings import settings

def get_chunk_text(chunk_id: str) -> Optional[str]:
    client = QdrantClient(url=str(settings.qdrant_url))
    flt = Filter(must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))])
    pts, _ = client.scroll(collection_name="kb_chunks", scroll_filter=flt, with_payload=True, limit=1)
    if not pts:
        return None
    payload = pts[0].payload or {}
    return payload.get("text")

def resolve_evidence(ev: Dict) -> Dict:
    cid = (ev or {}).get("source_chunk_id")
    if not cid:
        return {"chunk_id": None, "text": None}
    return {"chunk_id": cid, "text": get_chunk_text(cid)}
