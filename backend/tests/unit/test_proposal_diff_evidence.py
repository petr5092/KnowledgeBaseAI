from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.services.diff import build_diff
import json

def test_diff_contains_evidence():
    ensure_tables()
    evidence = {"source_chunk_id":"SC-123","quote":"hello"}
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="E-N1", properties_delta={"type":"Concept","uid":"E-N1","name":"N1"}, evidence=evidence),
    ]
    p = create_draft_proposal("tenant-e", 0, ops)
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
            (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])),
        )
    conn.close()
    df = build_diff(p.proposal_id)
    item = df["items"][0]
    assert "evidence" in item and item["evidence"]["quote"] == "hello"
