from app.services.integrity import check_prereq_cycles, check_dangling_skills, integrity_check_subgraph

def test_prereq_cycle_detection():
    rels = [
        {"type": "PREREQ", "from_uid": "A", "to_uid": "B"},
        {"type": "PREREQ", "from_uid": "B", "to_uid": "C"},
        {"type": "PREREQ", "from_uid": "C", "to_uid": "A"},
    ]
    cycles = check_prereq_cycles(rels)
    assert len(cycles) >= 3

def test_dangling_skills_detection():
    nodes = [
        {"type": "Skill", "uid": "S1"},
        {"type": "Skill", "uid": "S2"},
        {"type": "Concept", "uid": "C1"},
    ]
    rels = [
        {"type": "BASED_ON", "from_uid": "S1", "to_uid": "C1"},
    ]
    dangling = check_dangling_skills(nodes, rels)
    assert dangling == ["S2"]

def test_integrity_check_subgraph():
    nodes = [{"type": "Skill", "uid": "S1"}, {"type": "Concept", "uid": "C1"}]
    rels = [{"type": "BASED_ON", "from_uid": "S1", "to_uid": "C1"}]
    res = integrity_check_subgraph(nodes, rels)
    assert res["ok"] is True

def test_canon_compliance():
    # Invalid node type
    nodes = [{"type": "InvalidType", "uid": "X1"}]
    rels = []
    res = integrity_check_subgraph(nodes, rels)
    assert res["ok"] is False
    assert "canon_violations" in res
    assert len(res["canon_violations"]) > 0

    # Invalid edge type
    nodes = [{"type": "Concept", "uid": "C1"}, {"type": "Concept", "uid": "C2"}]
    rels = [{"type": "INVALID_REL", "from_uid": "C1", "to_uid": "C2"}]
    res = integrity_check_subgraph(nodes, rels)
    assert res["ok"] is False
    assert len(res["canon_violations"]) > 0
    
    # Valid case
    nodes = [{"type": "Concept", "uid": "C1"}]
    rels = []
    res = integrity_check_subgraph(nodes, rels)
    assert res["ok"] is True
