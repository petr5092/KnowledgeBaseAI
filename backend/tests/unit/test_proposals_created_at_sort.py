from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn, list_proposals
import json, time

def test_list_sorted_by_created_at_desc():
    ensure_tables()
    tenant = "tenant-sort"
    ops = [Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="X1", properties_delta={"type":"Concept","uid":"X1","name":"A"}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    p1 = create_draft_proposal(tenant, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p1.proposal_id, p1.tenant_id, p1.base_graph_version, p1.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    time.sleep(0.05)
    ops2 = [Operation(op_id="2", op_type=OpType.CREATE_NODE, target_id="X2", properties_delta={"type":"Concept","uid":"X2","name":"B"}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    p2 = create_draft_proposal(tenant, 0, ops2)
    conn2 = get_conn(); conn2.autocommit=True
    with conn2.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p2.proposal_id, p2.tenant_id, p2.base_graph_version, p2.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops2])))
    conn2.close()
    items = list_proposals(tenant, ProposalStatus.DRAFT.value, limit=10, offset=0)
    assert items[0]["proposal_id"] == p2.proposal_id
