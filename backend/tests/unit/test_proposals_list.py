from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn, list_proposals
import json

def test_list_proposals_by_tenant_and_status():
    ensure_tables()
    ops = [Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="L-DEMO", properties_delta={"type":"Concept","uid":"L-DEMO","name":"List Demo"}, evidence={"source_chunk_id":"SC-1","quote":"q"})]
    p = create_draft_proposal("tenant-l", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    items = list_proposals("tenant-l", ProposalStatus.DRAFT.value, limit=10, offset=0)
    assert len(items) >= 1 and items[0]["tenant_id"] == "tenant-l"
