from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.workers.commit import commit_proposal
from src.workers.outbox_publisher import process_once
from src.events.publisher import get_redis
import json, uuid

def test_outbox_publisher_publishes_graph_committed():
    ensure_tables()
    tid = "tenant-obx"
    uid = "C-"+uuid.uuid4().hex[:6]
    ops = [Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id=uid, properties_delta={"type":"Concept","uid":uid,"name":"Outbox Concept"}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    r = get_redis()
    key = "events:graph_committed"
    before = r.llen(key)
    pr = process_once(limit=10)
    after = r.llen(key)
    assert pr["processed"] >= 1
    assert after == before + pr["processed"]
