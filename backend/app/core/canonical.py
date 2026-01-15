import json
import re
import unicodedata
from hashlib import sha256
from typing import Any

_WS_RE = re.compile(r"\s+")

def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = t.strip()
    t = _WS_RE.sub(" ", t)
    return t

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def hash_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return sha256(data).hexdigest()

def canonical_hash_from_text(text: str) -> str:
    return hash_sha256(normalize_text(text))

def canonical_hash_from_json(obj: Any) -> str:
    return hash_sha256(canonical_json(obj))

ALLOWED_NODE_LABELS = {
    "Subject", "Section", "Subsection", "Topic", "Skill", "Method",
    "Goal", "Objective", "Example", "Error", "ContentUnit",
    "Concept", "Formula", "TaskType"
}

ALLOWED_EDGE_TYPES = {
    "CONTAINS", "PREREQ", "USES_SKILL", "LINKED", "TARGETS",
    "HAS_EXAMPLE", "HAS_UNIT", "MEASURES", "BASED_ON"
}
