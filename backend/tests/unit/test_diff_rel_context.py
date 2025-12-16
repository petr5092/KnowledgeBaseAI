from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.services.diff import build_diff
from src.services.graph.neo4j_repo import get_driver
import json, uuid

def test_diff_rel_contains_from_to_context():
    ensure_tables()
    tid = "tenant-diff-rel"
    fu = "F-"+uuid.uuid4().hex[:6]
    tu = "T-"+uuid.uuid4().hex[:6]
    drv = get_driver()
    with drv.session() as s:
        s.run("MERGE (a:Concept {uid:$fu, tenant_id:$tid}) SET a.name='From'", {"fu": fu, "tid": tid})
        s.run("MERGE (b:Concept {uid:$tu, tenant_id:$tid}) SET b.name='To'", {"tu": tu, "tid": tid})
    drv.close()
    ops = [Operation(op_id="1", op_type=OpType.CREATE_REL, target_id="E-"+uuid.uuid4().hex[:6], properties_delta={"type":"PREREQ","from_uid":fu,"to_uid":tu,"weight":1.0}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    df = build_diff(p.proposal_id)
    item = [it for it in df["items"] if it["kind"]=="REL"][0]
    assert item["from_node"]["uid"] == fu and item["from_node"]["name"] == "From"
    assert item["to_node"]["uid"] == tu and item["to_node"]["name"] == "To"
