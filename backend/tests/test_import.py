from src.services.kb.jsonl_io import load_jsonl
import os

def test_load_jsonl_handles_missing(tmp_path):
    p = tmp_path / "not_exists.jsonl"
    data = load_jsonl(str(p))
    assert data == []
