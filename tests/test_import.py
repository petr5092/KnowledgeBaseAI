from neo4j_utils import _load_jsonl
import os

def test_load_jsonl_handles_missing(tmp_path):
    p = tmp_path / "not_exists.jsonl"
    data = _load_jsonl(str(p))
    assert data == []
