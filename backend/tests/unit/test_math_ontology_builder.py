import json
from src.services.kb.builder import build_mathematics_ontology, enrich_all_topics
from src.services.kb.jsonl_io import load_jsonl, get_path
from src.services.graph.utils import sync_from_jsonl
from src.db.pg import ensure_tables

def test_build_mathematics_ontology_jsonl():
    res = build_mathematics_ontology()
    assert res["ok"] is True
    subjects = load_jsonl(get_path("subjects.jsonl"))
    assert any((s.get("title") or "").strip().upper() == "МАТЕМАТИКА" for s in subjects)
    sections = load_jsonl(get_path("sections.jsonl"))
    subsections = load_jsonl(get_path("subsections.jsonl"))
    topics = load_jsonl(get_path("topics.jsonl"))
    prereqs = load_jsonl(get_path("topic_prereqs.jsonl"))
    assert len(sections) >= 10
    assert len(subsections) >= 10
    assert len(topics) >= 50
    assert len(prereqs) >= 40

def test_enrich_topics_and_import():
    ensure_tables()
    enrich = enrich_all_topics()
    assert enrich["ok"] is True
    res = sync_from_jsonl()
    assert "proposal_id" in res and isinstance(res["ops"], int) and res["ops"] > 100
