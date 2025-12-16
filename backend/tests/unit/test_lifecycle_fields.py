from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.workers.commit import commit_proposal
from src.services.graph.neo4j_repo import node_by_uid
import json

def test_created_node_has_lifecycle_and_created_at():
    ensure_tables()
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="C-LIFE", properties_delta={"type":"Concept","uid":"C-LIFE","name":"Life Concept"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
    ]
    p = create_draft_proposal("tenant-life", 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    props = node_by_uid("C-LIFE", "tenant-life")
    assert props.get("lifecycle_status") == "ACTIVE"
    assert isinstance(props.get("created_at"), str) and len(props.get("created_at")) > 0
