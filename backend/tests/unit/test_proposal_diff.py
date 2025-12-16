from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.db.pg import ensure_tables, get_conn
from src.services.diff import build_diff
import json

def test_build_diff_for_create_node_and_rel():
    ensure_tables()
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id="D-N1", properties_delta={"type":"Concept","uid":"D-N1","name":"N1"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="2", op_type=OpType.CREATE_REL, target_id="D-R1", properties_delta={"type":"PREREQ","from_uid":"D-N1","to_uid":"D-N2","weight":0.5}, evidence={"source_chunk_id":"SC-2","quote":"q2"}),
    ]
    p = create_draft_proposal("tenant-d", 0, ops)
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)",
            (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])),
        )
    conn.close()
    df = build_diff(p.proposal_id)
    assert isinstance(df.get("items"), list)
    assert any(it.get("kind")=="NODE" and it.get("before") is None for it in df["items"])
    assert any(it.get("kind")=="REL" and it.get("type")=="PREREQ" for it in df["items"])
