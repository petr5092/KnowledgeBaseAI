from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.workers.commit import commit_proposal
from src.services.graph.neo4j_repo import get_driver
import json, uuid

def test_relation_evidence_creates_sourcechunk_and_evidenced_by_from_from_node():
    ensure_tables()
    tid = "tenant-rel-ev"
    fu = "A-"+uuid.uuid4().hex[:6]
    tu = "B-"+uuid.uuid4().hex[:6]
    drv = get_driver()
    with drv.session() as s:
        s.run("MERGE (a:Concept {uid:$fu, tenant_id:$tid}) SET a.name='A'", {"fu": fu, "tid": tid})
        s.run("MERGE (b:Concept {uid:$tu, tenant_id:$tid}) SET b.name='B'", {"tu": tu, "tid": tid})
    drv.close()
    ev = {"source_chunk_id":"CH-"+uuid.uuid4().hex[:8],"quote":"rel evidence"}
    ops = [Operation(op_id="1", op_type=OpType.CREATE_REL, target_id="E-"+uuid.uuid4().hex[:6], properties_delta={"type":"PREREQ","from_uid":fu,"to_uid":tu,"weight":1.0}, evidence=ev)]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    drv = get_driver()
    with drv.session() as s:
        c1 = s.run("MATCH (a {uid:$fu, tenant_id:$t})-[:EVIDENCED_BY]->(sc:SourceChunk {uid:$cid, tenant_id:$t}) RETURN COUNT(sc) AS c", {"fu": fu, "t": tid, "cid": ev["source_chunk_id"]}).single()["c"]
        assert c1 >= 1
    drv.close()
