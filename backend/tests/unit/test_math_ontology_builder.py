import json
from app.services.kb.builder import build_mathematics_ontology, enrich_all_topics
from app.services.kb.jsonl_io import load_jsonl, get_path
from app.db.pg import ensure_tables

def test_build_mathematics_ontology_jsonl():
    res = build_mathematics_ontology()
    assert res["ok"] is True
    subjects = load_jsonl(get_path("subjects.jsonl"))
    assert any((s.get("title") or "").strip().upper() == "MATH" for s in subjects)
    sections = load_jsonl(get_path("sections.jsonl"))
    subsections = load_jsonl(get_path("subsections.jsonl"))
    topics = load_jsonl(get_path("topics.jsonl"))
    prereqs = load_jsonl(get_path("topic_prereqs.jsonl"))
    assert len(sections) >= 10
    assert len(subsections) >= 10
    assert len(topics) >= 50
    assert len(prereqs) >= 40

def test_enrich_topics_jsonl_only():
    # This test only checks if JSONL files are updated, without importing to graph
    enrich = enrich_all_topics()
    assert enrich["ok"] is True
