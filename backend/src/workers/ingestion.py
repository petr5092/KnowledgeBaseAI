import unicodedata
import re
import uuid
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from src.config.settings import settings
try:
    from prometheus_client import Counter
    INGESTION_SUCCESS_TOTAL = Counter("ingestion_success_total", "Total successful ingested chunks")
except Exception:
    class _Dummy:
        def inc(self, n=1): ...
    INGESTION_SUCCESS_TOTAL = _Dummy()

_WS = re.compile(r"\s+")

def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = t.strip()
    t = _WS.sub(" ", t)
    return t

def chunk_text(text: str, max_len: int = 256) -> List[Dict]:
    words = text.split(" ")
    chunks = []
    cur = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + 1 > max_len and cur:
            cid = "CH-" + uuid.uuid4().hex[:12]
            chunks.append({"chunk_id": cid, "text": " ".join(cur)})
            cur = []
            cur_len = 0
        cur.append(w)
        cur_len += len(w) + 1
    if cur:
        cid = "CH-" + uuid.uuid4().hex[:12]
        chunks.append({"chunk_id": cid, "text": " ".join(cur)})
    return chunks

def _hash16(text: str) -> List[float]:
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(16):
        v = int.from_bytes(h[i*2:(i+1)*2], "big") / 65535.0
        vec.append(v)
    return vec

def ensure_collection(client: QdrantClient, name: str, size: int = 16):
    cols = [c.name for c in client.get_collections().collections]
    if name not in cols:
        client.create_collection(name, vectors_config=VectorParams(size=size, distance=Distance.COSINE))

def embed_chunks(tenant_id: str, doc_id: str, chunks: List[Dict], collection: str = "kb_chunks") -> int:
    client = QdrantClient(url=str(settings.qdrant_url))
    ensure_collection(client, collection, 16)
    points = []
    for ch in chunks:
        vec = _hash16(ch["text"])
        pid = uuid.uuid4().int % (10**12)
        points.append(PointStruct(id=pid, vector=vec, payload={"tenant_id": tenant_id, "chunk_id": ch["chunk_id"], "doc_id": doc_id, "text": ch["text"]}))
    if points:
        client.upsert(collection_name=collection, points=points)
        INGESTION_SUCCESS_TOTAL.inc(len(points))
    return len(points)
