from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn, outbox_fetch_unpublished
from src.workers.commit import commit_proposal
import json, uuid

def test_commit_writes_outbox_event():
    ensure_tables()
    tid = "tenant-outbox"
    uid = "C-"+uuid.uuid4().hex[:6]
    ops = [Operation(op_id="1", op_type=OpType.MERGE_NODE, target_id=uid, properties_delta={"type":"Concept","uid":uid,"name":"Outbox Concept"})]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    evs = outbox_fetch_unpublished(limit=10)
    assert any(e.get("event_type")=="graph_committed" for e in evs)
