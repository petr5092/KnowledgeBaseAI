from services.question_selector import select_examples_for_topics

def test_select_examples_empty_env(monkeypatch):
    monkeypatch.delenv('NEO4J_URI', raising=False)
    monkeypatch.delenv('NEO4J_USER', raising=False)
    monkeypatch.delenv('NEO4J_PASSWORD', raising=False)
    res = select_examples_for_topics(topic_uids=["TOP-X"], limit=3)
    assert isinstance(res, list)
