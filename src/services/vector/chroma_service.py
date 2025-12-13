from typing import List, Tuple
from chromadb import Client
from chromadb.config import Settings as ChromaSettings
from src.core.config import settings
from openai import AsyncOpenAI

client = Client(ChromaSettings(chroma_api_impl="rest", chroma_server_host=settings.chroma_host, chroma_server_http_port=settings.chroma_port))
collection = client.get_or_create_collection(name="concepts")
oai = AsyncOpenAI(api_key=settings.openai_api_key)

async def embed_text(text: str) -> List[float]:
    resp = await oai.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding

async def upsert_concept(uid: str, title: str, definition: str, embedding: List[float]) -> None:
    collection.upsert(ids=[uid], embeddings=[embedding], metadatas=[{"title": title, "definition": definition}])

def query_similar(embedding: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
    res = collection.query(query_embeddings=[embedding], n_results=top_k)
    ids = res.get("ids", [[]])[0]
    dists = res.get("distances", [[]])[0]
    return list(zip(ids, dists))
