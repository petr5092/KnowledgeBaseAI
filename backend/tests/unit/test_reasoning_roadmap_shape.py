from src.services.reasoning.roadmap import build_roadmap

def test_roadmap_shape():
    res = build_roadmap(subject_uid="MATH-EGE", progress={}, goals=None, prereq_threshold=0.7, top_k=5)
    assert isinstance(res, dict)
    assert "items" in res and "meta" in res
    assert isinstance(res["items"], list)
