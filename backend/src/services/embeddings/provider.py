from typing import List
import hashlib

class HashEmbeddingProvider:
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
