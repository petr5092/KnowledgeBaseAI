from src.services.roadmap_planner import plan_route
from src.services.graph.neo4j_repo import get_driver

def test_plan_route_orders_by_priority():
    drv = get_driver()
    tid = "tenant-roadmap"
    sub = "SUB-1"
    sec = "SEC-1"
    a = "T-A"
    b = "T-B"
    c = "T-C"
    with drv.session() as s:
        s.run("MERGE (sub:Subject {uid:$su, tenant_id:$t})", {"su": sub, "t": tid})
        s.run("MERGE (sec:Section {uid:$se, tenant_id:$t})", {"se": sec, "t": tid})
        s.run("MATCH (sub:Subject {uid:$su, tenant_id:$t}), (sec:Section {uid:$se, tenant_id:$t}) MERGE (sub)-[:CONTAINS]->(sec)", {"su": sub, "se": sec, "t": tid})
        s.run("MERGE (a:Topic {uid:$a, tenant_id:$t}) SET a.title='A'", {"a": a, "t": tid})
        s.run("MERGE (b:Topic {uid:$b, tenant_id:$t}) SET b.title='B'", {"b": b, "t": tid})
        s.run("MERGE (c:Topic {uid:$c, tenant_id:$t}) SET c.title='C'", {"c": c, "t": tid})
        s.run("MATCH (sec:Section {uid:$se, tenant_id:$t}), (a:Topic {uid:$a, tenant_id:$t}) MERGE (sec)-[:CONTAINS]->(a)", {"se": sec, "a": a, "t": tid})
        s.run("MATCH (sec:Section {uid:$se, tenant_id:$t}), (b:Topic {uid:$b, tenant_id:$t}) MERGE (sec)-[:CONTAINS]->(b)", {"se": sec, "b": b, "t": tid})
        s.run("MATCH (sec:Section {uid:$se, tenant_id:$t}), (c:Topic {uid:$c, tenant_id:$t}) MERGE (sec)-[:CONTAINS]->(c)", {"se": sec, "c": c, "t": tid})
        s.run("MATCH (b:Topic {uid:$b, tenant_id:$t}), (a:Topic {uid:$a, tenant_id:$t}) MERGE (b)-[:PREREQ]->(a)", {"a": a, "b": b, "t": tid})
        s.run("MATCH (c:Topic {uid:$c, tenant_id:$t}), (b:Topic {uid:$b, tenant_id:$t}) MERGE (c)-[:PREREQ]->(b)", {"b": b, "c": c, "t": tid})
    drv.close()
    progress = {a: 0.9, b: 0.2, c: 0.0}
    res = plan_route(sub, progress, limit=3, penalty_factor=0.2)
    assert len(res) >= 3
    assert res[0]["uid"] in (b, c)
    assert res[-1]["uid"] == a
