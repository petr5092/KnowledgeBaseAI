from src.services.reasoning.next_best_topic import next_best_topics

def test_next_best_topic_shape():
    res = next_best_topics(subject_uid="MATH-EGE", progress={}, prereq_threshold=0.7, top_k=5)
    assert isinstance(res, dict)
    assert "items" in res
    assert isinstance(res["items"], list)
