from src.db.pg import ensure_tables, get_conn
from src.schemas.proposal import Operation, OpType, ProposalStatus
from src.services.proposal_service import create_draft_proposal
from src.workers.commit import commit_proposal
import json, uuid

def test_graph_changes_insert_includes_change_type():
    ensure_tables()
    tid = "tenant-changes"
    nuid = "N-"+uuid.uuid4().hex[:6]
    euid = "E-"+uuid.uuid4().hex[:6]
    ops = [
        Operation(op_id="1", op_type=OpType.CREATE_NODE, target_id=nuid, properties_delta={"type":"Concept","uid":nuid,"name":"A"}, evidence={"source_chunk_id":"SC-1","quote":"q"}),
        Operation(op_id="2", op_type=OpType.CREATE_REL, target_id=euid, properties_delta={"type":"LINKED","from_uid":nuid,"to_uid":"N-"+uuid.uuid4().hex[:6]}, evidence={"source_chunk_id":"SC-2","quote":"rel"}),
    ]
    p = create_draft_proposal(tid, 0, ops)
    conn = get_conn(); conn.autocommit=True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO proposals (proposal_id, tenant_id, base_graph_version, proposal_checksum, status, operations_json) VALUES (%s,%s,%s,%s,%s,%s)", (p.proposal_id, p.tenant_id, p.base_graph_version, p.proposal_checksum, ProposalStatus.DRAFT.value, json.dumps([o.model_dump() for o in ops])))
    conn.close()
    res = commit_proposal(p.proposal_id)
    assert res["ok"] is True
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT change_type FROM graph_changes WHERE tenant_id=%s ORDER BY graph_version DESC LIMIT 2", (tid,))
        rows = cur.fetchall()
    conn.close()
    assert rows and len(rows) >= 1
    types = {r[0] for r in rows}
    assert "NODE" in types or "REL" in types
