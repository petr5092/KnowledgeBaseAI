from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn, get_proposal, get_graph_version
from src.workers.commit import commit_proposal

def test_approve_and_commit_flow():
    ensure_tables()
    ops = [Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="R-DEMO", properties_delta={"type":"Concept","uid":"R-DEMO","name":"Review Demo"}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    gv = get_graph_version("tenant-r")
    p = create_draft_proposal("tenant-r", gv, ops)
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        import json
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    pr = get_proposal(p.proposal_id)
    assert pr["status"] in (ProposalStatus.DONE.value, ProposalStatus.COMMITTING.value, "DONE")
