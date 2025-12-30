from typing import List
import hashlib
import os

class BaseEmbeddingProvider:
    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

class HashEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dim: int = 16):
        self.dim = int(dim)

    def embed_text(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        need = self.dim * 2
        buf = (h * ((need // len(h)) + 1))[:need]
        vec: List[float] = []
        for i in range(self.dim):
            v = int.from_bytes(buf[i*2:(i+1)*2], "big") / 65535.0
            vec.append(v)
        return vec

class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dim: int = 1536, model: str = "text-embedding-3-small", api_key: str | None = None):
        self.dim = int(dim)
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or ""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY missing for embedding provider")

    def embed_text(self, text: str) -> List[float]:
        import httpx
        url = "https://api.openai.com/v1/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"input": text, "model": self.model}
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            vec = data["data"][0]["embedding"]
            if self.dim and len(vec) != self.dim:
                if len(vec) > self.dim:
                    vec = vec[: self.dim]
                else:
                    pad = [0.0] * (self.dim - len(vec))
                    vec = vec + pad
            return vec

def get_provider(dim_default: int = 16) -> BaseEmbeddingProvider:
    mode = os.environ.get("EMBEDDINGS_MODE", "hash").lower()
    dim = int(dim_default)
    if mode == "model":
        try:
            return OpenAIEmbeddingProvider(dim=dim)
        except Exception:
            return HashEmbeddingProvider(dim=dim)
    return HashEmbeddingProvider(dim=dim)
