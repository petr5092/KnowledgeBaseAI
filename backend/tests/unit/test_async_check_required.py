import os
from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.workers.commit import commit_proposal
import json

def test_async_check_triggers_on_threshold():
    ensure_tables()
    os.environ["INTEGRITY_CHECK_THRESHOLD_MS"] = "1"
    os.environ["INTEGRITY_TEST_SLEEP_MS"] = "20"
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="C-ASYNC", properties_delta={"type":"Concept","uid":"C-ASYNC","name":"Async"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
    ]
    p = create_draft_proposal("tenant-async", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is False and res["status"] == "ASYNC_CHECK_REQUIRED"
