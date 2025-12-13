from src.services.roadmap_planner import plan_route

def test_plan_route_basic(monkeypatch):
    class DummySession:
        def run(self, q, params=None):
            return type("Rows", (), {"data": lambda self: [
                {"uid": "TOP-A", "title": "A", "prereqs": []},
                {"uid": "TOP-B", "title": "B", "prereqs": ["TOP-A"]},
            ]})()
    class DummyDrv:
        def session(self): return DummySession()
        def close(self): pass
    from src.services.graph import neo4j_repo
    neo4j_repo.get_driver = lambda: DummyDrv()
    items = plan_route(None, {"TOP-A": 0.0, "TOP-B": 0.0}, limit=10)
    assert items[0]["uid"] in {"TOP-A", "TOP-B"}
    assert isinstance(items, list)
