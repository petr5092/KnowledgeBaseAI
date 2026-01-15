import os, json, uuid
from app.schemas.proposal import Operation, OpType, ProposalStatus
from app.services.proposal_service import create_draft_proposal
from app.db.pg import ensure_tables, get_conn
from app.workers.commit import commit_proposal

def test_commit_fails_on_skill_based_on_exceeding_max():
    ensure_tables()
    os.environ["INTEGRITY_SKILL_BASE_MIN"] = "1"
    os.environ["INTEGRITY_SKILL_BASE_MAX"] = "1"
    tid = "tenant-base-rule"
    s = "S-"+uuid.uuid4().hex[:6]
    c1 = "C-"+uuid.uuid4().hex[:6]
    c2 = "C-"+uuid.uuid4().hex[:6]
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id=s, properties_delta={"type":"Skill","uid":s,"name":"Skill"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="2", op_type=OpType.CREATE_NODE, target_id=c1, properties_delta={"type":"Concept","uid":c1,"name":"C1"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="3", op_type=OpType.CREATE_NODE, target_id=c2, properties_delta={"type":"Concept","uid":c2,"name":"C2"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="4", op_type=OpType.CREATE_REL, target_id="E-"+uuid.uuid4().hex[:6], properties_delta={"type":"BASED_ON","from_uid":s,"to_uid":c1}, evidence={"source_chunk_id":"SC-2","quote":"rel"}),
        Operation(op_id="5", op_type=OpType.CREATE_REL, target_id="E-"+uuid.uuid4().hex[:6], properties_delta={"type":"BASED_ON","from_uid":s,"to_uid":c2}, evidence={"source_chunk_id":"SC-3","quote":"rel"}),
    ]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is False
    assert res["status"] == "FAILED"
    assert "skill_base_rules" in res.get("violations", {})
