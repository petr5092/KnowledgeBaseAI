from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import os

def apply_vector_schema():
    url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    name = os.environ.get("QDRANT_COLLECTION", "kb_entities")
    dim = int(os.environ.get("QDRANT_DEFAULT_VECTOR_DIM", "16"))
    client = QdrantClient(url=url)
    cols = [c.name for c in client.get_collections().collections]
    if name not in cols:
        client.create_collection(name, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        return {"created": True, "name": name, "dim": dim}
    info = client.get_collection(name)
    current = int(info.result.config.params.vectors.size)  # type: ignore
    return {"created": False, "name": name, "dim": current}

if __name__ == "__main__":
    print(apply_vector_schema())
