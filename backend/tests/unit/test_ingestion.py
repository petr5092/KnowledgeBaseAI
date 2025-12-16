from src.workers.ingestion import normalize_text, chunk_text, embed_chunks
from qdrant_client import QdrantClient
from src.config.settings import settings

def test_parse_and_chunk():
    raw = "  Hello\tWorld  " + ("x " * 300)
    norm = normalize_text(raw)
    assert "Hello World" in norm
    chunks = chunk_text(norm, max_len=64)
    assert len(chunks) >= 3
    assert all("chunk_id" in c and "text" in c for c in chunks)

def test_embed_chunks_into_qdrant():
    text = "alpha beta gamma delta " * 50
    chunks = chunk_text(normalize_text(text), max_len=128)
    n = embed_chunks("tenant-ut", "doc-1", chunks)
    assert n == len(chunks)
    client = QdrantClient(url=str(settings.qdrant_url))
    res = client.scroll(collection_name="kb_chunks", with_payload=True, limit=10)[0]
    assert isinstance(res, list)
