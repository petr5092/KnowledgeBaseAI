from src.services.embeddings.provider import HashEmbeddingProvider

def test_hash_embedding_provider_dim():
    p8 = HashEmbeddingProvider(dim=8)
    v8 = p8.embed_text("hello")
    assert len(v8) == 8
    p16 = HashEmbeddingProvider(dim=16)
    v16 = p16.embed_text("hello")
    assert len(v16) == 16
