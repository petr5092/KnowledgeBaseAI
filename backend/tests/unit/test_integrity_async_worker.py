from src.db.pg import ensure_tables, get_conn
from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.workers.integrity_async import process_once
import json

def test_integrity_async_marks_ready_for_valid_ops():
    ensure_tables()
    tid = "tenant-async-ok"
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="S-AOK", properties_delta={"type":"Skill","uid":"S-AOK","name":"Skill"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="2", op_type=OpType.CREATE_NODE, target_id="C-AOK", properties_delta={"type":"Concept","uid":"C-AOK","name":"Concept"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="3", op_type=OpType.CREATE_REL, target_id="E-AOK", properties_delta={"type":"BASED_ON","from_uid":"S-AOK","to_uid":"C-AOK"}, evidence={"source_chunk_id":"SC-2","quote":"rel"})
    ]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, "ASYNC_CHECK_REQUIRED", json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = process_once(limit=10)
    assert res["processed"] >= 1
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM proposals WHERE proposal_id=%s", (p.proposal_id,))
        st = cur.fetchone()[0]
    conn.close()
    assert st == "READY"
